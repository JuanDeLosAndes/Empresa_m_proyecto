from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from app import create_app, database
from app.repositories.imagen_maquina_repository import ImagenesGridFS
from app.repositories.imagen_proxy_repository import ImagenesProxyConCache
from app.documentos.store import get_mongo_database


@pytest.fixture
def sitio(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "prueba.db")
    monkeypatch.setattr(database.Database, "_instance", None)
    return create_app()


def cuenta(sitio, nombre, empresa=False):
    cliente = TestClient(sitio)
    datos = {"correo": nombre + "@example.org", "contrasena": "ClaveDePrueba12345678!"}
    if empresa:
        ruta = "/registro/empresa"
        datos.update(nombre_empresa=nombre, nit={"Alquileres": "900123456", "Equipos": "900123457"}[nombre])
    else:
        ruta = "/registro/persona"
        datos.update(usuario=nombre, cedula=nombre)
    with patch("app.controllers.auth_controller.enviar_verificacion") as enviar:
        assert cliente.post(ruta, data=datos).status_code == 200
    correo, token = enviar.call_args.args
    assert correo == datos["correo"].lower()
    respuesta = cliente.post("/verificar-correo", data={"token": token}, follow_redirects=False)
    assert respuesta.headers["location"] == "/?registro=ok"
    assert cliente.post("/login", data={"identificador": datos["correo"], "contrasena": datos["contrasena"]},
                        follow_redirects=False).headers["location"] == "/?login=ok"
    return cliente


def test_carrito_y_cotizacion(sitio):
    anonimo = TestClient(sitio)
    for ruta in ("/carrito", "/checkout"):
        respuesta = anonimo.get(ruta)
        assert respuesta.status_code == 200
        assert 'data-auth-panel="login">' in respuesta.text
    persona = cuenta(sitio, "persona")
    db = database.get_connection()
    comercial = db.execute("SELECT * FROM maquinarias WHERE costo_por_hora > 0 LIMIT 1").fetchone()
    especial = db.execute("SELECT id_maquinaria FROM maquinarias WHERE costo_por_hora = 0 LIMIT 1").fetchone()[0]
    base = "/api/carrito/items"
    for ruta in (base, "/api/carrito/agregar"):
        assert persona.post(ruta, json={"id_maquinaria": especial}).status_code == 409
    assert persona.get("/api/carrito/cantidad").json()["cantidad"] == 0
    registro = {"id_maquinaria": comercial["id_maquinaria"], "horas": 2}
    assert persona.post(base, json=registro).is_success
    assert persona.post(base, json=registro).is_success
    assert persona.get("/api/carrito/cantidad").json()["cantidad"] == 1
    ruta = f"{base}/{comercial['id_maquinaria']}"
    assert persona.patch(ruta, json={"horas": 0}).status_code == 422
    datos = persona.patch(ruta, json={"horas": 3}).json()
    subtotal = comercial["costo_por_hora"] * 3
    assert datos["horas"] == 3
    assert datos["total_linea"] == datos["subtotal"] == subtotal
    assert datos["total"] == pytest.approx(subtotal * 1.19)
    assert persona.delete(ruta).is_success
    assert persona.get("/api/carrito/cantidad").json()["cantidad"] == 0
    solicitud = dict(id_maquinaria=especial, nombre="Andrea", email="a@example.org", telefono="3001234567")
    assert anonimo.post("/cotizaciones", json={**solicitud, "email": "mal"}).status_code == 422
    respuesta = anonimo.post("/cotizaciones", json=solicitud)
    assert respuesta.status_code == 201
    fila = db.execute("SELECT * FROM cotizaciones WHERE id_cotizacion = ?", (respuesta.json()["id_cotizacion"],)).fetchone()
    assert fila["id_maquinaria"] == especial and fila["nombre"] == "Andrea"


def test_empresa_solo_gestiona_su_equipo(sitio):
    persona = cuenta(sitio, "Andrea")
    empresa = cuenta(sitio, "Alquileres", True)
    otra = cuenta(sitio, "Equipos", True)
    db = database.get_connection()
    usuario = db.execute("SELECT id_usuario FROM usuarios WHERE nombre='Andrea'").fetchone()[0]
    destino = db.execute("SELECT id_empresa FROM empresas WHERE nombre='Alquileres'").fetchone()[0]
    ruta = "/api/empresa/solicitudes"
    decision = f"{ruta}/{usuario}"
    integrante = f"/api/empresa/integrantes/{usuario}"
    for aceptar in (False, True):
        assert persona.post(ruta, json={"id_empresa": destino}).status_code == 201
        assert persona.post(ruta, json={"id_empresa": destino}).status_code == 409
        assert "Andrea" in empresa.get("/mi-empresa").text
        assert otra.patch(decision, json={"aceptar": True}).status_code == 404
        assert empresa.patch(decision, json={"aceptar": aceptar}).is_success
    assert persona.delete(integrante).status_code == 403
    assert otra.delete(integrante).status_code == 404
    assert "Perteneces a" in persona.get("/mi-empresa").text
    assert empresa.delete(integrante).is_success
    assert "Seleccionar empresa" in persona.get("/mi-empresa").text


@pytest.mark.parametrize("usar_proxy", [False, True])
def test_contrato_de_almacenamiento(usar_proxy):
    real = ImagenesGridFS(get_mongo_database())
    almacen = ImagenesProxyConCache(real) if usar_proxy else real
    archivo = "prueba-contrato.jpg"
    assert almacen.guardar(archivo, b"foto")
    assert not almacen.guardar(archivo, b"foto")
    assert almacen.obtener(archivo).contenido == b"foto"
    almacen.guardar(archivo, b"nueva")
    assert almacen.obtener(archivo).contenido == b"nueva"
    almacen.eliminar(archivo)
    assert almacen.obtener(archivo) is None