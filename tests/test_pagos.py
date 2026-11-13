"""Pruebas de la pasarela de pagos: flujo simulado, firma Wompi y verificación del monto."""
import hashlib
import os

import httpx
import pytest
from fastapi.testclient import TestClient

from app import create_app
from app.database import get_connection
from app.models.pago import PagoModel
from app.pagos.wompi import PasarelaWompi
from app.pagos.pasarela import SolicitudPago


@pytest.fixture(scope="module")
def client():
    os.environ.setdefault("MSPS_PASARELA", "simulada")
    with TestClient(create_app()) as c:
        yield c


def _maquina_con_tarifa():
    fila = get_connection().execute(
        "SELECT id_maquinaria FROM maquinarias WHERE costo_por_hora > 0 LIMIT 1"
    ).fetchone()
    if fila is None:
        pytest.skip("No hay máquinas con tarifa en la base de datos")
    return fila["id_maquinaria"]


def _login_admin(client):
    r = client.post("/login", data={"identificador": "admin",
                                    "contrasena": os.environ.get("MSPS_ADMIN_PASSWORD", "admin123")},
                    follow_redirects=False)
    assert r.status_code == 303


def _preparar_carrito(client):
    client.post("/api/carrito/agregar", json={"id_maquinaria": _maquina_con_tarifa(), "horas": 2})


def test_iniciar_pago_exige_sesion(client):
    cliente_anonimo = TestClient(client.app)
    assert cliente_anonimo.post("/api/pagos/iniciar").status_code == 401


def test_flujo_simulado_aprobado_vacia_carrito(client):
    _login_admin(client)
    _preparar_carrito(client)

    r = client.post("/api/pagos/iniciar")
    assert r.status_code == 200
    url = r.json()["url"]
    referencia = url.rsplit("/", 1)[-1]
    assert url == f"/pago/simulado/{referencia}"

    pago = PagoModel.obtener_por_referencia(referencia)
    assert pago.estado == "pendiente" and pago.monto > 0

    assert client.get(url).status_code == 200
    r = client.post(url, data={"decision": "aprobar"}, follow_redirects=False)
    assert r.status_code == 303

    r = client.get(f"/pago/retorno/{referencia}")
    assert r.status_code == 200
    assert "Pago aprobado" in r.text
    assert client.get("/api/carrito/cantidad").json()["cantidad"] == 0


def test_pago_rechazado_conserva_carrito(client):
    _login_admin(client)
    _preparar_carrito(client)
    url = client.post("/api/pagos/iniciar").json()["url"]
    referencia = url.rsplit("/", 1)[-1]

    client.post(url, data={"decision": "rechazar"}, follow_redirects=False)
    r = client.get(f"/pago/retorno/{referencia}")
    assert "Pago rechazado" in r.text
    assert client.get("/api/carrito/cantidad").json()["cantidad"] >= 1


def test_no_se_puede_ver_el_pago_de_otro_usuario(client):
    _login_admin(client)
    _preparar_carrito(client)
    url = client.post("/api/pagos/iniciar").json()["url"]
    referencia = url.rsplit("/", 1)[-1]

    otro = TestClient(client.app)
    assert otro.get(f"/pago/retorno/{referencia}", follow_redirects=False).status_code in (302, 404)


def test_firma_integridad_wompi_sigue_la_formula_oficial():
    pasarela = PasarelaWompi("pub_test_x", "secreto123", "https://api-sandbox.co.uat.wompi.dev/v1")
    esperada = hashlib.sha256(b"MSPS-ABC12345" + b"30000000" + b"COP" + b"secreto123").hexdigest()
    assert pasarela.firma_integridad("MSPS-ABC12345", 30000000) == esperada


def test_wompi_inicio_incluye_firma_y_monto_en_centavos():
    pasarela = PasarelaWompi("pub_test_x", "secreto123", "https://api-sandbox.co.uat.wompi.dev/v1")
    inicio = pasarela.iniciar(SolicitudPago("MSPS-REF1", 150000, "http://localhost/ret"))
    assert "amount-in-cents=15000000" in inicio.url_pago
    assert "signature%3Aintegrity=" in inicio.url_pago


def test_wompi_verificar_rechaza_transaccion_de_otro_pedido(monkeypatch):
    class Resp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"data": {"status": "APPROVED", "reference": "OTRO", "amount_in_cents": 100}}

    monkeypatch.setattr(httpx, "get", lambda *a, **k: Resp())
    pasarela = PasarelaWompi("pub", "sec", "https://x/v1")
    assert pasarela.verificar("MSPS-REF1", "tx-1").estado == "error"


def test_wompi_verificar_aprobado(monkeypatch):
    class Resp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"data": {"status": "APPROVED", "reference": "MSPS-REF1", "amount_in_cents": 15000000}}

    monkeypatch.setattr(httpx, "get", lambda *a, **k: Resp())
    pasarela = PasarelaWompi("pub", "sec", "https://x/v1")
    res = pasarela.verificar("MSPS-REF1", "tx-1")
    assert res.estado == "aprobado" and res.monto_pesos == 150000


def test_wompi_sin_id_de_transaccion_queda_pendiente():
    pasarela = PasarelaWompi("pub", "sec", "https://x/v1")
    assert pasarela.verificar("MSPS-REF1", None).estado == "pendiente"
