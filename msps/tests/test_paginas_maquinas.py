"""Pruebas de extremo a extremo: las páginas leen fotos y ficha desde MongoDB."""
import re

import pytest
from fastapi.testclient import TestClient

from app import create_app
from app.database import get_connection


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as c:  # el arranque corre el seed (SQL + MongoDB)
        yield c


def _id_por_placa(placa):
    fila = get_connection().execute(
        "SELECT id_maquinaria FROM maquinarias WHERE placa = ?", (placa,)
    ).fetchone()
    return fila["id_maquinaria"]


def test_listado_muestra_portadas_servidas_desde_mongodb(client):
    r = client.get("/maquinas")
    assert r.status_code == 200
    assert "/media/maquinas/john-deere-200g-mc770043/01.jpg" in r.text
    assert "/static/images/maquinas/" not in r.text
    assert "Tarifa por cotizar" in r.text


def test_detalle_muestra_galeria_y_cuadro_de_informacion(client):
    r = client.get(f"/maquina/{_id_por_placa('MC770043')}")
    assert r.status_code == 200
    html = r.text
    assert len(re.findall(r'class="detalle-miniatura(?: activa)?"', html)) == 6
    assert "20.788 kg" in html and "7,07 m" in html
    assert "Solo por cotización" in html  # sin tarifa cargada


def test_cada_foto_de_cada_maquina_se_descarga_desde_mongodb(client):
    from app.catalogo_maquinas import construir_catalogo

    for doc in construir_catalogo():
        for img in doc.imagenes:
            r = client.get(f"/media/maquinas/{img.archivo}")
            assert r.status_code == 200, img.archivo
            assert r.headers["content-type"] == "image/jpeg"
            assert r.content[:3] == b"\xff\xd8\xff", img.archivo  # firma JPEG


def test_etag_evita_reenviar_la_foto(client):
    url = "/media/maquinas/komatsu-pc130/01.jpg"
    etag = client.get(url).headers["etag"]
    r = client.get(url, headers={"If-None-Match": etag})
    assert r.status_code == 304 and r.content == b""


def test_foto_inexistente_da_404_y_las_fotos_ya_no_son_archivos_estaticos(client):
    assert client.get("/media/maquinas/no/existe.jpg").status_code == 404
    assert client.get("/static/images/maquinas/komatsu-pc130/01.jpg").status_code == 404


def test_seed_es_idempotente_no_duplica_documentos_ni_fotos(client):
    from app.seed import seed_catalogo_real
    from app.documentos.store import get_mongo_database

    base = get_mongo_database()
    antes = (base["maquinas"].count_documents({}), base["fs.files"].count_documents({}))
    seed_catalogo_real()
    seed_catalogo_real()
    assert (base["maquinas"].count_documents({}), base["fs.files"].count_documents({})) == antes == (9, 22)


def test_detalle_de_demo_sin_documento_sigue_funcionando(client):
    r = client.get(f"/maquina/{_id_por_placa('MSP-001')}")
    assert r.status_code == 200
    assert "Ficha técnica" not in r.text
    assert "Agregar al carrito" in r.text
