from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app import create_app, database
from app.models.carrito import (
    CarritoModel, ConsultaMaquinaria, LineaCarrito, MaquinaNoDisponible,
    RequiereCotizacion, ResumenCarrito,
)
from app.models.maquinaria import Maquinaria
from app.repositories.carrito_repository import CarritoRepositorioBase


def equipo(tarifa, disponible=True):
    return Maquinaria(id_maquinaria=1, marca="Prueba", descripcion=None, capacidad=None,
                      modelo="QA", costo_por_hora=tarifa, placa="QA-01", id_categoria=1,
                      disponible=disponible)


@pytest.mark.parametrize("disponible,tarifa,error", [
    (True, 100, None),
    (True, 0, RequiereCotizacion),
    (False, 100, MaquinaNoDisponible),
    (False, 0, MaquinaNoDisponible),
])
def test_decision_de_alquiler(disponible, tarifa, error):
    almacen = Mock(spec=CarritoRepositorioBase)
    almacen.leer.return_value = []
    catalogo = Mock(spec=ConsultaMaquinaria)
    catalogo.obtener_por_id.return_value = equipo(tarifa, disponible)
    carrito = CarritoModel(almacen, catalogo)
    if error:
        with pytest.raises(error):
            carrito.agregar(1, 2)
        almacen.guardar.assert_not_called()
    else:
        carrito.agregar(1, 2)
        items, = almacen.guardar.call_args.args
        assert [(item.id_maquinaria, item.horas) for item in items] == [(1, 2)]


def test_iva_redondea_medio_centavo_en_el_total():
    resumen = ResumenCarrito([LineaCarrito(equipo(100.50), 1)])
    assert (resumen.subtotal, resumen.iva, resumen.total) == (100.50, 19.10, 119.60)


def test_manual_swagger_publica_rutas_y_parametros(motor_sql):
    with TestClient(create_app()) as cliente:
        docs = cliente.get("/docs")
        assert docs.status_code == 200 and "/openapi.json" in docs.text
        esquema = cliente.get("/openapi.json")
        assert esquema.status_code == 200
        rutas = esquema.json()["paths"]
        for ruta, metodos in {
            "/api/maquinas/{id_maquinaria}/estimacion": {"get"},
            "/admin/maquinas": {"post"},
            "/admin/maquinas/{id_maquinaria}": {"put", "delete"},
            "/api/carrito/items/{id_maquinaria}": {"patch", "delete"},
        }.items():
            assert metodos <= rutas[ruta].keys()
            if "{id_maquinaria}" in ruta:
                for metodo in metodos:
                    assert any(p["name"] == "id_maquinaria" and p["in"] == "path" and p["required"]
                               for p in rutas[ruta][metodo]["parameters"])


def test_baja_de_equipo_se_refleja_en_catalogo_y_api(motor_sql, monkeypatch):
    clave = "Temporal12345678!"
    monkeypatch.setenv("MSPS_ADMIN_PASSWORD", clave)
    with TestClient(create_app()) as admin:
        login = admin.post("/login", data={"identificador": "admin", "contrasena": clave},
                           headers={"Accept": "application/json"})
        assert login.status_code == 200 and login.json()["ok"]
        with database.transaccion() as db:
            categoria = db.execute("SELECT MIN(id_categoria) AS id FROM categorias").fetchone()["id"]
        datos = dict(marca="EquipoQA", modelo="Entrega", placa="QA-ENTREGA", costo_por_hora=80,
                     id_categoria=categoria, ficha_tecnica={"Potencia": "80 kW"})
        alta = admin.post("/admin/maquinas", json=datos)
        assert alta.status_code == 201
        ident = alta.json()["id_maquinaria"]
        ruta = f"/admin/maquinas/{ident}"
        estimacion = f"/api/maquinas/{ident}/estimacion"
        assert admin.get(estimacion, params={"horas": 0}).status_code == 422
        assert admin.get(estimacion, params={"horas": 1}).json()["total_linea"] == 80
        assert admin.put(ruta, json={"costo_por_hora": 90, "ficha_tecnica": {"Potencia": "95 kW"}}).status_code == 200
        assert "95 kW" in admin.get(f"/maquina/{ident}").text
        assert admin.get(estimacion, params={"horas": 2}).json()["total_linea"] == 180
        assert admin.delete(ruta).status_code == 200
        assert admin.get(estimacion, params={"horas": 1}).status_code == 404
        assert admin.get(f"/maquina/{ident}").status_code == 404
        catalogo = admin.get("/maquinas")
        assert catalogo.status_code == 200 and "EquipoQA Entrega" not in catalogo.text