from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pymongo.errors import ServerSelectionTimeoutError

from app.catalogo_maquinas import construir_catalogo
from app.documentos.fichas import FichaExcavadora, FichaTecnicaFactory
from app.documentos.maquina_documento import MaquinaDocumentoBuilder
from app.documentos.store import MongoConnection, get_mongo_database
from app.repositories.imagen_maquina_repository import (
    ImagenesEscritor,
    ImagenesGridFS,
    ImagenesLector,
)
from app.repositories.maquina_documentos_repository import (
    MaquinaDocumentosEscritor,
    MaquinaDocumentosLector,
    MaquinaDocumentosMongo,
)

SEMILLA = Path(__file__).resolve().parent.parent / "app" / "seed_data" / "imagenes_maquinas"


@pytest.fixture
def base_datos():
    """Base MongoDB aislada por prueba (se limpia al terminar)."""
    base = get_mongo_database().client[f"aislada_{id(object())}"]
    yield base
    base.client.drop_database(base.name)


@pytest.fixture
def repo(base_datos):
    r = MaquinaDocumentosMongo(base_datos)
    r.asegurar_indices()
    return r


@pytest.fixture
def imagenes(base_datos):
    return ImagenesGridFS(base_datos)


# ---------------- Singleton ----------------
def test_singleton_devuelve_siempre_la_misma_instancia():
    assert MongoConnection() is MongoConnection()


# ---------------- Factory Method ----------------
def test_factory_crea_la_ficha_segun_el_tipo():
    assert isinstance(FichaTecnicaFactory.crear("excavadora"), FichaExcavadora)
    assert FichaTecnicaFactory.crear("minicargador").tipo == "minicargador"


def test_factory_rechaza_tipo_y_campos_invalidos():
    with pytest.raises(ValueError):
        FichaTecnicaFactory.crear("submarino")
    with pytest.raises(ValueError):
        FichaTecnicaFactory.crear("excavadora", velocidad_warp=9)


def test_ficha_formatea_numeros_en_colombiano_y_omite_vacios():
    filas = FichaTecnicaFactory.crear(
        "excavadora", peso_operativo=20788, profundidad_max_excavacion=7.07, motor=None
    ).filas_cuadro_info()
    assert {"etiqueta": "Peso operativo", "valor": "20.788 kg"} in filas
    assert {"etiqueta": "Profundidad máx. de excavación", "valor": "7,07 m"} in filas
    assert all(f["etiqueta"] != "Motor" for f in filas)


# ---------------- Builder ----------------
def _builder():
    return MaquinaDocumentoBuilder().con_identidad("X1", "Marca", "M1", "Excavadora")


def test_builder_rechaza_imagen_repetida():
    b = _builder().agregar_imagen("a.jpeg", "v", "alt")
    with pytest.raises(ValueError):
        b.agregar_imagen("a.jpeg", "v", "alt")


def test_builder_exige_imagen_y_una_sola_portada():
    with pytest.raises(ValueError):
        _builder().build()
    with pytest.raises(ValueError):
        _builder().agregar_imagen("a", "v", "x", portada=True).agregar_imagen(
            "b", "v", "x", portada=True
        ).build()


def test_builder_pone_la_portada_primero_y_numera_los_archivos():
    doc = (
        _builder()
        .agregar_imagen("a", "v", "x")
        .agregar_imagen("b", "v", "x", portada=True)
        .build()
    )
    assert [i.origen for i in doc.imagenes] == ["b", "a"]
    assert [i.archivo.split("/")[1] for i in doc.imagenes] == ["01.jpg", "02.jpg"]
    assert doc.portada.origen == "b"


def test_builder_se_puede_reutilizar_tras_build():
    b = _builder().agregar_imagen("a", "v", "x")
    b.build()
    with pytest.raises(ValueError):
        b.build()  # estado reiniciado: sin identidad ni imágenes


# ---------------- Catálogo real ----------------
def test_ninguna_foto_se_usa_en_dos_maquinas():
    docs = construir_catalogo()
    origenes = [i.origen for d in docs for i in d.imagenes]
    assert len(origenes) == 22
    assert len(origenes) == len(set(origenes))


def test_placas_y_slugs_son_unicos():
    docs = construir_catalogo()
    assert len({d.placa for d in docs}) == len(docs)
    assert len({d.slug for d in docs}) == len(docs)


def test_cada_imagen_del_catalogo_existe_en_la_carpeta_semilla():
    for d in construir_catalogo():
        for i in d.imagenes:
            assert (SEMILLA / i.archivo).is_file(), i.archivo


# ---------------- Repositorio de documentos (SOLID) ----------------
def test_repositorio_cumple_las_interfaces_segregadas(repo, imagenes):
    assert isinstance(repo, MaquinaDocumentosLector)
    assert isinstance(repo, MaquinaDocumentosEscritor)
    assert isinstance(imagenes, ImagenesLector)
    assert isinstance(imagenes, ImagenesEscritor)


def test_guardar_es_idempotente_y_ida_y_vuelta_exacta(repo):
    doc = construir_catalogo()[3]
    assert repo.guardar(doc) is True
    assert repo.guardar(doc) is False  # sin cambios: no escribe
    leido = repo.obtener_por_placa(doc.placa)
    assert leido.to_document() == doc.to_document()
    assert len(repo.listar()) == 1


def test_portadas_por_placa(repo):
    for d in construir_catalogo():
        repo.guardar(d)
    portadas = repo.portadas_por_placa()
    assert len(portadas) == 9
    assert all(p.portada for p in portadas.values())


def test_el_indice_unico_por_slug_impide_duplicados(repo):
    from pymongo.errors import DuplicateKeyError

    doc = construir_catalogo()[0]
    repo.guardar(doc)
    with pytest.raises(DuplicateKeyError):
        repo._col.insert_one({"slug": doc.slug, "placa": "OTRA"})


def test_si_mongodb_cae_la_lectura_devuelve_vacio_en_vez_de_romper():
    base = MagicMock()
    base.__getitem__.return_value.find_one.side_effect = ServerSelectionTimeoutError("caído")
    base.__getitem__.return_value.find.side_effect = ServerSelectionTimeoutError("caído")
    r = MaquinaDocumentosMongo(base)
    assert r.obtener_por_placa("X") is None
    assert r.listar() == []
    assert r.portadas_por_placa() == {}
    with pytest.raises(ServerSelectionTimeoutError):  # la escritura NO esconde el error
        r.guardar(construir_catalogo()[0])


# ---------------- Imágenes en GridFS ----------------
def test_la_foto_se_guarda_dentro_de_mongodb_y_se_lee_igual(imagenes):
    original = (SEMILLA / "john-deere-200g-mc770043/01.jpg").read_bytes()
    assert imagenes.guardar("john-deere-200g-mc770043/01.jpg", original) is True
    leida = imagenes.obtener("john-deere-200g-mc770043/01.jpg")
    assert leida.contenido == original
    assert leida.tipo_contenido == "image/jpeg"
    assert len(leida.sha256) == 64


def test_subir_la_misma_foto_no_duplica_y_una_distinta_la_reemplaza(imagenes):
    assert imagenes.guardar("a/01.jpg", b"uno") is True
    assert imagenes.guardar("a/01.jpg", b"uno") is False
    assert imagenes.guardar("a/01.jpg", b"dos") is True
    assert imagenes.obtener("a/01.jpg").contenido == b"dos"


def test_foto_inexistente_devuelve_none(imagenes):
    assert imagenes.obtener("no/existe.jpg") is None
