import subprocess
from hashlib import sha256
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from app import create_app, factories
from app.documentos.store import get_mongo_database
from app.models.recursos_web import RECURSOS, RecursoWeb, RecursoWebNoDisponible
from app.repositories.recurso_web_repository import RecursosWebMongo
from tools.migrar_imagenes_web import IMAGENES, importar, retirar, verificar


@pytest.fixture
def lote(tmp_path, monkeypatch):
    datos = b"imagen de prueba"
    huella = sha256(datos).hexdigest()
    recurso = RecursoWeb("demo.webp", "image/webp", len(datos), huella, huella)
    ruta = "hero/prueba.png"
    monkeypatch.setitem(RECURSOS, ruta, recurso)
    paquete = tmp_path / "fotos.zip"
    with ZipFile(paquete, "w") as salida:
        salida.writestr(recurso.paquete, datos)
    factories.leer_imagen_web.cache_clear()
    yield ruta, datos, paquete, {ruta: recurso}, RecursosWebMongo(get_mongo_database())
    factories.leer_imagen_web.cache_clear()


def test_migracion_y_respuestas_http(lote, monkeypatch):
    ruta, datos, paquete, recursos, repo = lote
    url = "/static/images/" + ruta
    with TestClient(create_app()) as cliente:
        assert cliente.get(url).status_code == 503
        importar(paquete, repo, recursos)
        importar(paquete, repo, recursos)
        verificar(repo, recursos)
        assert repo.coleccion.count_documents({}) == 1
        r = cliente.get(url)
        assert r.status_code == 200 and r.content == datos
        assert r.headers["content-type"] == "image/webp"
        assert "max-age=" in r.headers["cache-control"]
        def lectura_inesperada(*args):
            raise AssertionError("La segunda petición debería usar la caché")
        monkeypatch.setattr(RecursosWebMongo, "leer", lectura_inesperada)
        assert cliente.get(url).content == datos
        assert cliente.get(url, headers={"If-None-Match": "W/" + r.headers["etag"]}).status_code == 304
        cabeza = cliente.head(url)
        assert cabeza.status_code == 200 and not cabeza.content
        assert int(cabeza.headers["content-length"]) == len(datos)
        assert cliente.get("/static/images/desconocida.jpg").status_code == 404
        assert cliente.get("/static/css/style.css").status_code == 200


def test_paquete_danado_no_se_importa(lote):
    ruta, datos, paquete, recursos, repo = lote
    with ZipFile(paquete, "w") as salida:
        salida.writestr(recursos[ruta].paquete, b"x" * len(datos))
    with pytest.raises(RecursoWebNoDisponible):
        importar(paquete, repo, recursos)
    assert repo.coleccion.count_documents({}) == 0


def test_retiro_respeta_los_originales_y_el_historial(lote, tmp_path):
    ruta, datos, paquete, recursos, repo = lote
    original = tmp_path / IMAGENES / ruta
    original.parent.mkdir(parents=True)
    original.write_bytes(datos)
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=tmp_path, text=True).strip()
    git("init", "-q")
    git("add", "--", IMAGENES.as_posix())
    git("-c", "user.name=Prueba", "-c", "user.email=prueba@example.test",
        "commit", "-qm", "Original")
    anterior = git("rev-parse", "HEAD")
    with pytest.raises(RecursoWebNoDisponible):
        retirar(tmp_path, repo, recursos)
    assert original.is_file()
    importar(paquete, repo, recursos)
    original.write_bytes(b"cambio local")
    with pytest.raises(ValueError, match="distinto"):
        retirar(tmp_path, repo, recursos)
    assert original.read_bytes() == b"cambio local"
    original.write_bytes(datos)
    retirar(tmp_path, repo, recursos)
    retirar(tmp_path, repo, recursos)
    assert not original.exists()
    assert git("rev-parse", "HEAD") == anterior
    assert git("diff", "--cached", "--name-only") == (IMAGENES / ruta).as_posix()


def test_desde_originales_crea_respaldo_y_permite_reimportar(tmp_path):
    import json
    from PIL import Image
    from tools.migrar_imagenes_web import desde_originales

    raiz = tmp_path / "proyecto"
    ruta = "hero/muestra.png"
    foto = raiz / IMAGENES / ruta
    foto.parent.mkdir(parents=True)
    Image.new("RGBA", (22, 18), (255, 100, 50, 125)).save(foto)
    huella = sha256(foto.read_bytes()).hexdigest()
    manifiesto = raiz / "catalogo.json"
    repo = RecursosWebMongo(get_mongo_database())
    desde_originales(raiz, tmp_path, manifiesto, repo, [ruta])
    recurso = RecursoWeb(**json.loads(manifiesto.read_text())[ruta])
    assert recurso.original == huella and recurso.tipo == "image/webp"
    paquete, = tmp_path.glob("MSPS_imagenes_*.zip")
    repo.coleccion.delete_one({"_id": recurso.sha256})
    importar(paquete, repo, {ruta: recurso})
    verificar(repo, {ruta: recurso})
    assert sha256(foto.read_bytes()).hexdigest() == huella


def test_fallo_de_verificacion_conserva_manifiesto_y_foto(tmp_path, monkeypatch):
    from PIL import Image
    from tools.migrar_imagenes_web import desde_originales

    raiz = tmp_path / "proyecto"
    ruta = "logo/logo-msps.png"
    foto = raiz / IMAGENES / ruta
    foto.parent.mkdir(parents=True)
    Image.new("RGB", (12, 12), "orange").save(foto)
    manifiesto = raiz / "catalogo.json"
    manifiesto.write_text("anterior")
    repo = RecursosWebMongo(get_mongo_database())

    def fallo(recurso):
        raise RecursoWebNoDisponible("Fallo simulado al verificar la carga")

    monkeypatch.setattr(repo, "leer", fallo)
    with pytest.raises(RecursoWebNoDisponible):
        desde_originales(raiz, tmp_path, manifiesto, repo, [ruta])
    assert manifiesto.read_text() == "anterior" and foto.is_file()