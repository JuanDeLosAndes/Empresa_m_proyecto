from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pymongo.errors import ServerSelectionTimeoutError

from app import create_app, database
from app.documentos.imagen import ImagenesLector
from app.documentos.store import get_mongo_database
from app.factories import crear_carrito, crear_imagenes_repositorio
from app.models.almacen import AlmacenNoDisponible
from app.models.carrito import CarritoModel, MaquinaNoDisponible
from app.models.galeria_maquina import GaleriaMaquinaModel
from app.models.maquinaria import MaquinariaModel
from app.repositories.imagen_maquina_repository import ImagenesGridFS
from app.repositories.maquina_documentos_repository import MaquinaDocumentosMongo


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "revision.db")
    monkeypatch.setattr(database.Database, "_instance", None)
    with TestClient(create_app()) as cliente:
        yield cliente


def test_foto_caida_devuelve_503_y_se_recupera(cliente, monkeypatch):
    almacen = crear_imagenes_repositorio()
    almacen.guardar("regresion.jpg", b"foto", "image/jpeg")
    original = almacen._real._leer
    fallo = Mock(side_effect=ServerSelectionTimeoutError("interrupción"))
    monkeypatch.setattr(almacen._real, "_leer", fallo)

    respuesta = cliente.get("/media/maquinas/regresion.jpg")
    assert respuesta.status_code == 503
    assert respuesta.headers["retry-after"] == "15"
    assert respuesta.headers["cache-control"] == "no-store"
    assert "interrupción" not in respuesta.text

    # Una lectura fallida no se almacena como si el archivo estuviera ausente.
    monkeypatch.setattr(almacen._real, "_leer", original)
    from app.documentos import store
    monkeypatch.setattr(store, "_disponibilidad", store.DisponibilidadMongo())
    respuesta = cliente.get("/media/maquinas/regresion.jpg")
    assert respuesta.status_code == 200 and respuesta.content == b"foto"
    assert cliente.get("/media/maquinas/ausente.jpg").status_code == 404


@pytest.mark.parametrize("operacion", ["subir", "poner_portada", "eliminar"])
def test_edicion_no_trata_una_base_caida_como_documento_ausente(cliente, monkeypatch, operacion):
    repositorio = MaquinaDocumentosMongo(get_mongo_database())
    fallo = Mock(side_effect=ServerSelectionTimeoutError("interrupción"))
    monkeypatch.setattr(repositorio, "_recordar", fallo)
    imagenes = Mock()
    galeria = GaleriaMaquinaModel(repositorio, imagenes)
    maquina = MaquinariaModel.listar()[0]
    with pytest.raises(AlmacenNoDisponible):
        if operacion == "subir":
            galeria.subir(maquina, [])
        else:
            getattr(galeria, operacion)(maquina, "foto.jpg")
    imagenes.guardar.assert_not_called()
    imagenes.eliminar.assert_not_called()


def test_error_de_escritura_gridfs_se_traduce_en_el_repositorio(monkeypatch):
    repositorio = ImagenesGridFS(get_mongo_database())
    monkeypatch.setattr(repositorio._fs, "delete",
                        Mock(side_effect=ServerSelectionTimeoutError("interrupción")))
    with pytest.raises(AlmacenNoDisponible):
        repositorio.eliminar("foto.jpg")


def test_media_acepta_una_dependencia_de_solo_lectura(cliente):
    lector = Mock(spec=ImagenesLector)
    lector.obtener.return_value = None
    cliente.app.dependency_overrides[crear_imagenes_repositorio] = lambda: lector
    try:
        assert cliente.get("/media/maquinas/ausente.jpg").status_code == 404
        lector.obtener.assert_called_once_with("ausente.jpg")
    finally:
        cliente.app.dependency_overrides.clear()


def test_detalle_y_estimacion_comparten_el_modelo_inyectado(cliente):
    maquina = MaquinariaModel.listar()[0]
    carrito = Mock(spec=CarritoModel)
    carrito.estimar.return_value.horas = 1
    carrito.estimar.return_value.total = 12345.0
    cliente.app.dependency_overrides[crear_carrito] = lambda: carrito
    try:
        pagina = cliente.get(f"/maquina/{maquina.id_maquinaria}")
        assert pagina.status_code == 200
        assert pagina.context["estimacion_inicial"] == 12345.0
        respuesta = cliente.get(f"/api/maquinas/{maquina.id_maquinaria}/estimacion?horas=1")
        assert respuesta.json() == {"horas": 1, "total_linea": 12345.0}
        assert carrito.estimar.call_count == 2
        carrito.estimar.side_effect = MaquinaNoDisponible("Fuera de servicio")
        pagina = cliente.get(f"/maquina/{maquina.id_maquinaria}")
        assert pagina.status_code == 200 and pagina.context["estimacion_inicial"] is None
        assert cliente.get(f"/api/maquinas/{maquina.id_maquinaria}/estimacion?horas=1").status_code == 409
    finally:
        cliente.app.dependency_overrides.clear()