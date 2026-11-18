import copy
import hashlib
import re
import sqlite3
from io import BytesIO
from urllib.parse import parse_qs, urlsplit
from unittest.mock import Mock

import httpx
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from pymongo.errors import ServerSelectionTimeoutError

from app import create_app, database
from app.documentos.store import DisponibilidadMongo, MongoTemporalmenteNoDisponible, get_mongo_database
from app.factories import crear_galeria_maquina, crear_maquina_documentos_repositorio
from app.models.maquinaria import MaquinariaModel
from app.pagos.wompi import ConfiguracionWompi, ProveedorNoDisponible, Wompi
from app.security import SESSION_COOKIE_NAME, firmar_sesion


@pytest.fixture
def sitio(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "msps.db")
    monkeypatch.setattr(database.Database, "_instance", None)
    for clave, valor in {
        "WOMPI_AMBIENTE": "test", "WOMPI_PUBLIC_KEY": "pub_test_unidad",
        "WOMPI_PRIVATE_KEY": "prv_test_unidad", "WOMPI_INTEGRITY_SECRET": "test_integrity_unidad",
        "WOMPI_EVENTS_SECRET": "test_events_unidad", "PUBLIC_BASE_URL": "https://alquiler.example",
    }.items():
        monkeypatch.setenv(clave, valor)
    app = create_app()
    cliente = TestClient(app, base_url="https://alquiler.example")
    id_admin = database.get_connection().execute("SELECT id_usuario FROM usuarios WHERE nombre='admin'").fetchone()[0]
    cliente.cookies.set(SESSION_COOKIE_NAME, firmar_sesion("administrador", id_admin))
    return cliente


def preparar(cliente):
    maquina = next(m for m in MaquinariaModel.listar() if m.costo_por_hora > 0 and m.disponible)
    assert cliente.post("/api/carrito/items", json={"id_maquinaria": maquina.id_maquinaria, "horas": 2}).status_code == 200
    pagina = cliente.get("/checkout")
    csrf = re.search(r'name="csrf" value="([^"]+)"', pagina.text)[1]
    respuesta = cliente.post("/pagos/checkout", data={"csrf": csrf, "correo": "pagador@example.org"}, follow_redirects=False)
    assert respuesta.status_code == 303, respuesta.text
    parametros = parse_qs(urlsplit(respuesta.headers["location"]).query)
    return parametros, csrf, maquina


def evento(parametros, estado="APPROVED", importe=None):
    datos = {
        "id": "tx-123", "reference": parametros["reference"][0], "status": estado,
        "amount_in_cents": importe if importe is not None else int(parametros["amount-in-cents"][0]),
        "currency": "COP", "payment_method_type": "CARD",
    }
    timestamp = 1700000000
    firma = hashlib.sha256(f"tx-123{estado}{datos['amount_in_cents']}{timestamp}test_events_unidad".encode()).hexdigest()
    return {"event": "transaction.updated", "environment": "test", "timestamp": timestamp,
            "data": {"transaction": datos}, "signature": {"properties": ["transaction.id", "transaction.status", "transaction.amount_in_cents"], "checksum": firma}}


def test_checkout_no_confia_en_importes_del_navegador_y_reutiliza_pedido(sitio):
    parametros, csrf, maquina = preparar(sitio)
    assert int(parametros["amount-in-cents"][0]) == round(maquina.costo_por_hora * 2 * 1.19 * 100)
    texto = (parametros["reference"][0] + parametros["amount-in-cents"][0] + "COP"
             + parametros["expiration-time"][0] + "test_integrity_unidad")
    assert parametros["signature:integrity"][0] == hashlib.sha256(texto.encode()).hexdigest()
    segunda = sitio.post("/pagos/checkout", data={"csrf": csrf, "correo": "pagador@example.org", "total": 1}, follow_redirects=False)
    assert parse_qs(urlsplit(segunda.headers["location"]).query)["reference"] == parametros["reference"]
    assert "prv_test" not in segunda.headers["location"] and "test_events" not in segunda.headers["location"]
    assert sitio.post("/pagos/checkout", data={"csrf": "falso", "correo": "a@b.co"}).status_code == 403


def test_retorno_y_firma_falsa_no_aprueban_pagos(sitio, monkeypatch):
    p, _, _ = preparar(sitio)
    consulta = Mock()
    monkeypatch.setattr(Wompi, "consultar", consulta)
    referencia = p["reference"][0]
    assert "Esperando confirmación" in sitio.get(f"/pagos/resultado?referencia={referencia}&id=falso&status=APPROVED").text
    e = evento(p)
    e["signature"]["checksum"] = "0" * 64
    assert sitio.post("/api/pagos/wompi/eventos/test", json=e).status_code == 400
    consulta.assert_not_called()
    assert sitio.get("/api/pagos/" + referencia).json()["estado"] == "PENDING"
    otro = TestClient(sitio.app)
    otro.cookies.set(SESSION_COOKIE_NAME, firmar_sesion("empresa", 999))
    assert otro.get("/api/pagos/" + referencia).status_code == 401


def test_webhook_aprobado_idempotente_y_eventos_atrasados(sitio, monkeypatch):
    p, csrf, maquina = preparar(sitio)
    e = evento(p)
    monkeypatch.setattr(Wompi, "consultar", lambda self, ident: e["data"]["transaction"])
    for _ in range(2):
        assert sitio.post("/api/pagos/wompi/eventos/test", json=e).status_code == 200
    referencia = p["reference"][0]
    assert sitio.get("/api/pagos/" + referencia).json()["estado"] == "APPROVED"
    pago = database.get_connection().execute("SELECT * FROM pedidos_pago").fetchone()
    assert pago["pagada"] and pago["transaccion_id"] == "tx-123"
    assert database.get_connection().execute("SELECT COUNT(*) FROM pedidos_pago").fetchone()[0] == 1
    atrasado = evento(p, "PENDING")
    monkeypatch.setattr(Wompi, "consultar", lambda self, ident: atrasado["data"]["transaction"])
    assert sitio.post("/api/pagos/wompi/eventos/test", json=atrasado).status_code == 200
    assert sitio.get("/api/pagos/" + referencia).json()["estado"] == "APPROVED"
    # Se conserva una edición nueva del carrito hecha después de iniciar el pago.
    sitio.patch(f"/api/carrito/items/{maquina.id_maquinaria}", json={"horas": 3})
    assert sitio.post(f"/pagos/{referencia}/limpiar-carrito", data={"csrf": csrf}).status_code == 200
    assert sitio.get("/api/carrito/cantidad").json()["cantidad"] == 1


@pytest.mark.parametrize("campo,valor", [("amount_in_cents", 1), ("currency", "USD")])
def test_rechaza_transaccion_que_no_coincide(sitio, monkeypatch, campo, valor):
    p, _, _ = preparar(sitio)
    e = evento(p)
    transaccion = {**e["data"]["transaction"], campo: valor}
    monkeypatch.setattr(Wompi, "consultar", lambda self, ident: transaccion)
    assert sitio.post("/api/pagos/wompi/eventos/test", json=e).status_code == 400
    assert sitio.get("/api/pagos/" + p["reference"][0]).json()["estado"] == "PENDING"


def test_fallo_api_deja_pendiente_y_permite_reintento_de_webhook(sitio, monkeypatch):
    p, _, _ = preparar(sitio)
    def caido(*args):
        raise ProveedorNoDisponible("fallo")
    monkeypatch.setattr(Wompi, "consultar", caido)
    assert sitio.post("/api/pagos/wompi/eventos/test", json=evento(p)).status_code == 503
    assert sitio.get("/api/pagos/" + p["reference"][0]).json()["estado"] == "PENDING"


def test_ambiente_incorrecto_y_sin_configuracion(sitio, monkeypatch):
    p, csrf, _ = preparar(sitio)
    assert sitio.post("/api/pagos/wompi/eventos/prod", json=evento(p)).status_code == 400
    monkeypatch.delenv("WOMPI_EVENTS_SECRET")
    assert sitio.post("/pagos/checkout", data={"csrf": csrf, "correo": "a@b.co"}).status_code == 503
    assert "aún no están habilitados" in sitio.get("/checkout").text


def test_consulta_usa_llave_privada_solo_en_backend(monkeypatch, sitio):
    peticiones = []
    def manejar(request):
        peticiones.append(request)
        return httpx.Response(200, json={"data": {"id": "tx-123"}})
    real = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(manejar), **kw))
    assert Wompi(ConfiguracionWompi.desde_entorno()).consultar("tx-123")["id"] == "tx-123"
    assert peticiones[0].headers["Authorization"] == "Bearer prv_test_unidad"
    assert str(peticiones[0].url) == "https://sandbox.wompi.co/v1/transactions/tx-123"


def test_carrito_muestra_foto_propia_y_url_https_relativa(sitio):
    p, _, maquina = preparar(sitio)
    pagina = sitio.get("/carrito")
    assert '/static/images/sin-foto.svg' in pagina.text
    foto = BytesIO()
    Image.new("RGB", (80, 60), "orange").save(foto, "JPEG")
    galeria = crear_galeria_maquina()
    galeria.subir(maquina, [("nueva.jpg", foto.getvalue())])
    fotos = galeria.fotos_de(maquina)
    ruta = "/media/maquinas/" + fotos[0].archivo
    html = sitio.get("/carrito").text
    assert f'src="{ruta}"' in html
    assert 'src="http://' not in html
    assert sitio.get(ruta).status_code == 200


def test_cache_portadas_una_consulta_e_invalidacion(sitio, monkeypatch):
    repositorio = crear_maquina_documentos_repositorio()
    original = repositorio._col.find
    contador = Mock(wraps=original)
    monkeypatch.setattr(repositorio._col, "find", contador)
    repositorio.portadas_por_placa()
    repositorio.portadas_por_categoria()
    repositorio.portadas_por_placa()
    assert contador.call_count == 1
    maquina = MaquinariaModel.listar()[0]
    repositorio.actualizar_imagenes(maquina.placa, [])
    repositorio.portadas_por_placa()
    assert contador.call_count == 2


def test_mongo_caido_no_repite_la_espera_y_se_recupera():
    reloj = [0.0]
    circuito = DisponibilidadMongo(reloj=lambda: reloj[0])
    consulta = Mock(side_effect=ServerSelectionTimeoutError("fallo"))
    with pytest.raises(ServerSelectionTimeoutError):
        circuito.ejecutar(consulta)
    for _ in range(20):
        with pytest.raises(MongoTemporalmenteNoDisponible):
            circuito.ejecutar(consulta)
    assert consulta.call_count == 1
    reloj[0] = 16
    assert circuito.ejecutar(lambda: "recuperado") == "recuperado"


def test_empresa_con_mismo_id_no_puede_ver_pedido_de_otro_tipo(sitio):
    p, _, _ = preparar(sitio)
    with database.transaccion() as db:
        ident = db.execute("INSERT INTO empresas(nit,nombre,correo,contrasena_hash) VALUES ('900123456','Empresa','empresa@example.org','hash')").lastrowid
    cliente = TestClient(sitio.app)
    cliente.cookies.set(SESSION_COOKIE_NAME, firmar_sesion("empresa", ident))
    referencia = p["reference"][0]
    assert cliente.get("/api/pagos/" + referencia).status_code == 404
    assert cliente.get("/pagos/resultado?referencia=" + referencia).status_code == 404


def test_conciliacion_manual_solo_admin_y_no_confia_en_estado_cliente(sitio, monkeypatch):
    p, csrf, _ = preparar(sitio)
    e = evento(p)
    monkeypatch.setattr(Wompi, "consultar", lambda self, ident: e["data"]["transaction"])
    anonimo = TestClient(sitio.app)
    assert anonimo.post("/admin/pagos/conciliar", data={"csrf": csrf, "transaccion_id": "tx-123"}, follow_redirects=False).status_code == 303
    r = sitio.post("/admin/pagos/conciliar", data={"csrf": csrf, "transaccion_id": "tx-123"})
    assert r.status_code == 200 and "Pago aprobado" in r.text


def test_bootstrap_sqlite_no_sobrescribe_pedidos_al_reiniciar(tmp_path, monkeypatch):
    import os
    import shutil
    import subprocess
    import sys
    from pathlib import Path
    raiz = tmp_path / "copia"
    (raiz / "app").mkdir(parents=True)
    (raiz / "tools").mkdir()
    script = raiz / "tools" / "preparar_sqlite.py"
    shutil.copy(Path(__file__).resolve().parents[1] / "tools" / "preparar_sqlite.py", script)
    with sqlite3.connect(raiz / "app" / "msps.db") as db:
        db.execute("CREATE TABLE prueba(valor)")
        db.execute("INSERT INTO prueba VALUES ('inicial')")
    destino = raiz / "persistente" / "msps.db"
    entorno = {**os.environ, "MSPS_DB_PATH": str(destino)}
    subprocess.run([sys.executable, str(script)], env=entorno, check=True, capture_output=True)
    with sqlite3.connect(destino) as db:
        db.execute("UPDATE prueba SET valor='pago guardado'")
    subprocess.run([sys.executable, str(script)], env=entorno, check=True, capture_output=True)
    with sqlite3.connect(destino) as db:
        assert db.execute("SELECT valor FROM prueba").fetchone()[0] == 'pago guardado'