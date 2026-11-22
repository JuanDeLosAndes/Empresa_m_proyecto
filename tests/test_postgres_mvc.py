from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import sqlite3

from fastapi.testclient import TestClient
import pytest

from app import create_app, database
from app.factories import crear_consulta_pagos
from app.models import afiliacion, cotizacion, registro_verificado
from app.models.alquiler import AlquilerModel
from app.models.carrito import LineaCarrito, ResumenCarrito
from app.models.categoria import CategoriaModel
from app.models.diagnostico import campos_del_proyecto, estado_relacional
from app.models.empresa import EmpresaModel
from app.models.factura import FacturaModel
from app.models.factura_empresa import FacturaEmpresaModel
from app.models.maquinaria import MaquinariaModel
from app.models.pagos import PagosModel
from app.models.usuario import UsuarioModel
from app.repositories.pago_repository import PagoRepositorioSQL
from app.security import SESSION_COOKIE_NAME, firmar_sesion
from tools.importar_sqlite_a_postgres import importar, importar_catalogo


def test_esquema_relaciones_y_mvc(motor_sql, monkeypatch):
    sitio = create_app()
    cliente = TestClient(sitio)
    assert cliente.get("/admin/diagnostico", follow_redirects=False).status_code in (302, 303, 401, 403)
    with database.transaccion() as db:
        admin = db.execute("SELECT id_usuario FROM administradores").fetchone()["id_usuario"]
    cliente.cookies.set(SESSION_COOKIE_NAME, firmar_sesion("administrador", admin))
    informe = cliente.get("/admin/diagnostico").json()["relacional"]
    assert informe["motor"] == motor_sql and informe["ok"] and informe["faltantes"] == []
    assert informe["tablas"] == 15 and informe["campos"] == len(campos_del_proyecto()) == 99

    enviados = {}
    monkeypatch.setattr("app.controllers.auth_controller.enviar_verificacion", lambda correo, token: enviados.update({correo: token}))
    for tipo, nombre, correo, doc in [("persona", "Diana", "d@example.org", "101010"),
                                      ("empresa", "Constructora", "e@example.org", "900.123.456-7")]:
        campos = ({"usuario": nombre, "cedula": doc, "telefono": "3001234567"} if tipo == "persona"
                  else {"nombre_empresa": nombre, "nit": doc, "direccion": "Calle 10"})
        respuesta = cliente.post("/registro/" + tipo, data={**campos, "correo": correo, "contrasena": "Secreto812345678!"})
        assert respuesta.status_code == 200
        registro_verificado.confirmar(enviados[correo])
        with pytest.raises(ValueError):
            registro_verificado.confirmar(enviados[correo])
    persona = UsuarioModel.autenticar("d@example.org", "Secreto812345678!")
    empresa = EmpresaModel.autenticar("900123456-7", "Secreto812345678!")
    assert empresa.nit == "900123456" and empresa.direccion == "Calle 10"
    assert persona.telefono == "3001234567"
    afiliacion.solicitar(persona.id_usuario, empresa.id_empresa)
    afiliacion.resolver(empresa.id_empresa, persona.id_usuario, True)
    assert UsuarioModel.obtener_por_id(persona.id_usuario).id_empresa == empresa.id_empresa

    categoria = CategoriaModel.crear("Otra")
    m = MaquinariaModel.crear("Prueba", 120000.25, "TEST-PG", categoria.id_categoria, "Desc", "2 m³", "Modelo")
    importe = cliente.get(f"/api/maquinas/{m.id_maquinaria}/estimacion", params={"horas": 2}).json()
    assert importe == {"horas": 2, "total_linea": 240000.5}
    assert cliente.get(f"/maquina/{m.id_maquinaria}").status_code == 200
    c = cotizacion.registrar(m.id_maquinaria, "Diana", persona.correo, "3001000000", "Solicito cotización")
    assert c > 0
    a = AlquilerModel.crear("2026-01-01", persona.id_usuario, m.id_maquinaria, "2026-01-02")
    AlquilerModel.actualizar_estado_aprobacion(a.id_alquiler, "aprobado")
    assert AlquilerModel.obtener_por_id(a.id_alquiler).estado_aprobacion == "aprobado"
    assert FacturaModel.crear("F-001", persona.cedula, "PSE", 240000.5, 45600.1, a.id_alquiler).costo == 240000.5
    assert FacturaEmpresaModel.crear(empresa.nit, empresa.correo, "PSE", 240000.5, a.id_alquiler, empresa.id_empresa).id_empresa == empresa.id_empresa
    with pytest.raises(database.ERRORES_INTEGRIDAD):
        AlquilerModel.crear("2026-01-01", persona.id_usuario, -50)
    with pytest.raises(database.ERRORES_INTEGRIDAD):
        UsuarioModel.crear_persona_natural("Repetida", "Secreto812345678!", persona.cedula, "otra@example.org")
    assert UsuarioModel.autenticar("Repetida", "Secreto812345678!") is None
    with database.transaccion() as db:
        assert db.execute("SELECT 1 FROM usuarios WHERE nombre=?", ("Repetida",)).fetchone() is None
    MaquinariaModel.eliminar(m.id_maquinaria)
    assert cliente.get(f"/api/maquinas/{m.id_maquinaria}/estimacion?horas=2").status_code == 404
    with pytest.raises(LookupError):
        cotizacion.registrar(m.id_maquinaria, "Diana", persona.correo, "3001000000", "Otra")
    database.init_db()
    assert FacturaModel.listar_por_cedula(persona.cedula)[0].numero == "F-001"


def test_pedido_concurrente_y_privacidad(motor_sql):
    from types import SimpleNamespace
    categoria = CategoriaModel.crear("Equipo")
    equipo = MaquinariaModel.crear("M", 30000000, "ALTA", categoria.id_categoria)
    resumen = ResumenCarrito([LineaCarrito(equipo, 2)])
    sesion = {"tipo": "persona_natural", "id": 5, "nombre": "Comprador"}
    repositorio = PagoRepositorioSQL()
    pagos = PagosModel(repositorio, SimpleNamespace(ambiente="test"))
    with ThreadPoolExecutor(max_workers=3) as hilo:
        pedidos = list(hilo.map(lambda _: pagos.preparar(sesion, "p@example.org", resumen), range(6)))
    referencias = {p["referencia"] for p in pedidos}
    assert len(referencias) == 1
    p = pedidos[0]
    assert p["total_centavos"] == 7140000000
    consulta = crear_consulta_pagos()
    with pytest.raises(LookupError):
        consulta.obtener_visible(p["referencia"], {**sesion, "tipo": "empresa"})
    assert consulta.historial(sesion)[0]["referencia"] == p["referencia"]
    datos = {"id": "prueba", "status": "APPROVED", "payment_method_type": "PSE"}
    repositorio.actualizar(p["referencia"], datos, 123)
    assert consulta.lineas_pagadas(p["referencia"], sesion)[0]["horas"] == 2
    assert repositorio.actualizar(p["referencia"], {**datos, "status": "PENDING"}, 124)["estado"] == "APPROVED"


def test_importar_con_ids_y_sin_sobrescribir(postgres, tmp_path):
    origen = tmp_path / "origen.db"
    with closing(sqlite3.connect(origen)) as db:
        db.executescript(database.SCHEMA_PATH.read_text(encoding="utf-8"))
        db.execute("INSERT INTO categorias VALUES (75, 'Histórica')")
        db.execute("INSERT INTO categorias VALUES (100, 'De baja')")
        db.execute("DELETE FROM categorias WHERE id_categoria=100")
        db.execute("INSERT INTO maquinarias(id_maquinaria, id_categoria, marca, placa, costo_por_hora) VALUES (81, 75, 'Marca', 'X-1', 3.25)")
        db.execute("INSERT INTO cotizaciones VALUES (95, 81, 'C', 'a@example.org', '3001112233', 'Cotizar', '2026-01-02')")
        db.commit()
    antes = origen.read_bytes()
    conteos = importar(origen)
    assert conteos["cotizaciones"] == 1 and len(conteos) == 15
    assert MaquinariaModel.obtener_por_id(81).placa == "X-1"
    assert CategoriaModel.crear("Nueva").id_categoria == 101
    assert cotizacion.registrar(81, "B", "b@example.org", "3001112233", "Cotizar") == 96
    with pytest.raises(ValueError, match="ya contiene"):
        importar(origen)
    assert origen.read_bytes() == antes and estado_relacional()["faltantes"] == []


def test_importacion_incompleta_revierte_todas_las_tablas(postgres, tmp_path):
    origen = tmp_path / "incompleta.db"
    with closing(sqlite3.connect(origen)) as db:
        db.executescript(database.SCHEMA_PATH.read_text(encoding="utf-8"))
        db.execute("ALTER TABLE pedidos_pago RENAME COLUMN huella TO campo_inesperado")
    with pytest.raises(ValueError, match="pedidos_pago"):
        importar(origen)
    assert estado_relacional()["tablas"] == 0


def test_importar_solo_catalogo_no_traslada_cuentas_ni_pedidos(postgres, tmp_path, monkeypatch):
    origen = tmp_path / "catalogo.db"
    with closing(sqlite3.connect(origen)) as db:
        db.executescript(database.SCHEMA_PATH.read_text(encoding="utf-8"))
        db.execute("INSERT INTO categorias VALUES (75, 'Excavadora')")
        db.execute("INSERT INTO categorias VALUES (76, 'Equipo propio')")
        db.execute(
            """INSERT INTO maquinarias
               (id_maquinaria, id_categoria, marca, descripcion, capacidad, modelo,
                costo_por_hora, placa, disponible, eliminada)
               VALUES (81, 75, 'Hitachi', 'Orugas', '0,12 m³', 'ZX75', 85000,
                       'MSP-001', 1, 0)"""
        )
        db.execute(
            """INSERT INTO maquinarias
               (id_maquinaria, id_categoria, marca, placa, costo_por_hora, disponible, eliminada)
               VALUES (82, 76, 'Retirada', 'FOTO-82', 0, 0, 1)"""
        )
        db.execute(
            """INSERT INTO usuarios (id_usuario, nombre, contrasena_hash, id_rol)
               VALUES (42, 'Anterior', 'no-copiar',
                       (SELECT id_rol FROM roles WHERE nombre='administrador'))"""
        )
        db.commit()
    bytes_antes = origen.read_bytes()
    database.init_db()

    assert importar_catalogo(origen) == {"categorias": 2, "maquinarias": 2}
    assert importar_catalogo(origen) == {"categorias": 2, "maquinarias": 2}
    from app import seed
    monkeypatch.setattr(seed, "_sembrar_mongo", lambda catalogo: None)
    seed.seed_demo_data()
    with database.transaccion() as db:
        maquinas = db.execute(
            """SELECT m.*, c.nombre_categoria FROM maquinarias m
               JOIN categorias c ON c.id_categoria = m.id_categoria ORDER BY placa"""
        ).fetchall()
        categorias = db.execute("SELECT nombre_categoria FROM categorias ORDER BY nombre_categoria").fetchall()
        assert [fila["placa"] for fila in maquinas] == ["FOTO-82", "MSP-001"]
        assert [fila["nombre_categoria"] for fila in categorias] == ["Equipo propio", "Excavadora"]
        assert maquinas[0]["eliminada"] == 1 and maquinas[0]["disponible"] == 0
        assert maquinas[1]["marca"] == "Hitachi" and maquinas[1]["modelo"] == "ZX75"
        assert maquinas[1]["descripcion"] == "Orugas" and maquinas[1]["capacidad"] == "0,12 m³"
        assert maquinas[1]["costo_por_hora"] == 85000
        assert [fila["nombre"] for fila in db.execute("SELECT nombre FROM usuarios")] == ["admin"]
        assert db.execute("SELECT count(*) AS n FROM pedidos_pago").fetchone()["n"] == 0
    assert origen.read_bytes() == bytes_antes


def test_limites_mvc():
    import ast
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[1] / "app"
    for carpeta, prohibidos in {
        "controllers": ("app.database", "app.repositories", "app.documentos.store", "sqlite3", "psycopg", "pymongo"),
        "models": ("fastapi", "starlette", "app.controllers", "app.views"),
    }.items():
        for archivo in (raiz / carpeta).glob("*.py"):
            for nodo in ast.walk(ast.parse(archivo.read_text(encoding="utf-8"))):
                modulos = []
                if isinstance(nodo, ast.ImportFrom):
                    modulos = [nodo.module or ""]
                elif isinstance(nodo, ast.Import):
                    modulos = [n.name for n in nodo.names]
                for modulo in modulos:
                    assert not any(modulo == p or modulo.startswith(p + ".") for p in prohibidos), (archivo.name, modulo)

def test_importa_la_generacion_sqlite_del_repositorio(postgres, tmp_path):
    origen = tmp_path / "anterior.db"
    with closing(sqlite3.connect(origen)) as db:
        db.executescript(database.SCHEMA_PATH.read_text(encoding="utf-8"))
        db.execute("DROP TABLE pedidos_pago")
        db.execute("DROP TABLE registros_pendientes")
        db.execute("ALTER TABLE maquinarias DROP COLUMN eliminada")
        db.execute("INSERT INTO categorias VALUES (1, 'Excavadora')")
        db.execute("INSERT INTO maquinarias(id_maquinaria, id_categoria, marca, placa, costo_por_hora) VALUES (12, 1, 'Histórica', 'A-12', 90)")
        db.commit()
    antes = origen.read_bytes()
    conteos = importar(origen)
    assert conteos["pedidos_pago"] == conteos["registros_pendientes"] == 0
    assert MaquinariaModel.obtener_por_id(12).placa == "A-12"
    assert estado_relacional()["campos"] == 99 and antes == origen.read_bytes()