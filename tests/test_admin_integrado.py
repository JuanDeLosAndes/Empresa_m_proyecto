from io import BytesIO
import shutil
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from app import create_app, database
from app.models.usuario import UsuarioModel
from app.models.maquinaria import MaquinariaModel
from app.security import SESSION_COOKIE_NAME, firmar_sesion


@pytest.fixture
def clientes(tmp_path, monkeypatch):
    # A copy of the delivered SQLite DB exercises the migration with existing rows.
    archivo = tmp_path / "maquinas.db"
    shutil.copy(database.DB_PATH, archivo)
    monkeypatch.setattr(database, "DB_PATH", archivo)
    monkeypatch.setattr(database.Database, "_instance", None)
    app = create_app()
    admin = UsuarioModel.crear_administrador("Admin prueba", "prueba")
    cliente = TestClient(app)
    cliente.cookies.set(SESSION_COOKIE_NAME, firmar_sesion("administrador", admin.id_usuario))
    return cliente, TestClient(app)


def test_admin_crea_edita_y_sube_imagenes(clientes):
    admin, visitante = clientes
    conn = database.get_connection()
    categoria = conn.execute("SELECT id_categoria FROM categorias LIMIT 1").fetchone()[0]
    assert "data-abrir-alta" not in visitante.get("/maquinas").text
    for ruta in ("/", "/maquinas", "/maquinas?categoria=Excavadora", "/admin/maquinas"):
        respuesta = admin.get(ruta)
        assert respuesta.status_code == 200
        if ruta == "/":
            assert 'aria-label="Abrir catálogo"' in respuesta.text
        else:
            assert "data-abrir-alta" in respuesta.text
    datos = dict(marca="Prueba", modelo="Nueva", placa="PRUEBA-999", id_categoria=categoria,
                 ficha_tecnica={"Motor": "Diésel"}, costo_por_hora=95000, capacidad="1 m3", descripcion="Equipo de prueba", disponible=True)
    assert visitante.post("/admin/maquinas", json=datos, follow_redirects=False).status_code == 303
    sin_ficha = {k: v for k, v in datos.items() if k != "ficha_tecnica"}
    assert admin.post("/admin/maquinas", json=sin_ficha).status_code == 422
    r = admin.post("/admin/maquinas", json=datos)
    assert r.status_code == 201, r.text
    ident = r.json()["id_maquinaria"]
    assert admin.post("/admin/maquinas", json=datos).status_code == 409
    assert admin.post("/admin/maquinas", json={**datos, "placa": "OTRA", "costo_por_hora": -1}).status_code == 422
    edicion = dict(costo_por_hora=125000, capacidad="2 m3", descripcion="Actualizada", disponible=False)
    assert admin.put(f"/admin/maquinas/{ident}", json=edicion).status_code == 200
    maquina = MaquinariaModel.obtener_por_id(ident)
    assert (maquina.costo_por_hora, maquina.capacidad, maquina.descripcion, maquina.disponible) == (125000, "2 m3", "Actualizada", False)
    assert admin.post("/api/carrito/items", json={"id_maquinaria": ident}).status_code == 409
    assert maquina.ficha_tecnica == {"Motor": "Diésel"}
    assert "Diésel" in visitante.get(f"/maquina/{ident}").text
    assert "No disponible" in visitante.get(f"/maquina/{ident}").text
    assert 'id="form-editar-maquina"' not in visitante.get(f"/maquina/{ident}").text
    pagina = admin.get(f"/maquina/{ident}").text
    assert 'id="form-editar-maquina"' in pagina and 'id="subir-fotos-detalle"' in pagina
    for color in ("red", "blue"):
        foto = BytesIO()
        Image.new("RGB", (80, 80), color).save(foto, "JPEG")
        r = admin.post(f"/admin/maquinas/{ident}/fotos", files={"archivos": ("imagen.jpg", foto.getvalue(), "image/jpeg")})
        assert r.status_code == 200 and "Fotos subidas: 1." in r.text
    from app.factories import crear_galeria_maquina
    fotos = crear_galeria_maquina().fotos_de(maquina)
    assert len(fotos) == 2
    assert visitante.get("/media/maquinas/" + fotos[0].archivo).status_code == 200
    assert admin.put(f"/admin/maquinas/{ident}", json={**edicion, "disponible": True}).is_success
    assert admin.post("/api/carrito/items", json={"id_maquinaria": ident}).is_success


def test_persona_no_puede_editar_y_acceso_comun(clientes):
    admin, usuario = clientes
    UsuarioModel.crear_persona_natural(nombre="persona43", cedula="1010101043", correo="p43@example.org", contrasena="prueba")
    usuario.post("/login", data=dict(identificador="p43@example.org", contrasena="prueba"))
    maquina = MaquinariaModel.listar()[0]
    datos = dict(costo_por_hora=1, capacidad="", descripcion="", disponible=True)
    assert usuario.put(f"/admin/maquinas/{maquina.id_maquinaria}", json=datos).status_code == 403
    for ruta in ("/", "/maquinas", f"/maquina/{maquina.id_maquinaria}", "/mi-empresa", "/carrito", "/checkout"):
        respuesta = usuario.get(ruta)
        assert respuesta.status_code == 200
        assert 'class="equipo-acceso"' in respuesta.text