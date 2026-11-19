import os
import sys
import uuid
from tempfile import TemporaryDirectory
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Toda la suite usa una base desechable. La prueba PostgreSQL abre su propio esquema.
_sql_temporal = TemporaryDirectory(prefix="msps_pruebas_")
os.environ["MSPS_DB_ENGINE"] = "sqlite"
os.environ["MSPS_DB_PATH"] = str(Path(_sql_temporal.name) / "prueba.db")
Path(os.environ["MSPS_DB_PATH"]).touch()

_URI_REAL = os.environ.get("MSPS_TEST_MONGO_URI")
_NOMBRE_DB = f"msps_test_{uuid.uuid4().hex[:8]}"
os.environ["MONGODB_DB"] = _NOMBRE_DB

if _URI_REAL:
    os.environ["MONGODB_URI"] = _URI_REAL
else:
    os.environ['MONGODB_URI'] = 'mongodb://localhost:27017'
    import mongomock
    import mongomock.gridfs
    import pymongo

    mongomock.gridfs.enable_gridfs_integration()
    pymongo.MongoClient = mongomock.MongoClient


def pytest_sessionfinish(session, exitstatus):
    if _URI_REAL:
        from app.documentos.store import MongoConnection

        MongoConnection()._client.drop_database(_NOMBRE_DB)


import pytest


@pytest.fixture(autouse=True)
def aislar_caches_y_fallos(monkeypatch):
    from app.documentos import store
    from app import factories
    nombre = _NOMBRE_DB + "_" + uuid.uuid4().hex[:8]
    monkeypatch.setenv("MONGODB_DB", nombre)
    monkeypatch.setattr(store.MongoConnection, "_instance", None)
    monkeypatch.setattr(store, "_disponibilidad", store.DisponibilidadMongo())
    monkeypatch.setattr(factories, "_documentos", None)
    monkeypatch.setattr(factories, "_proxy_imagenes", None)
    yield
    if _URI_REAL and store.MongoConnection._instance is not None:
        store.get_mongo_database().client.drop_database(nombre)


@pytest.fixture
def postgres(monkeypatch):
    import psycopg
    from psycopg import sql
    from app import database

    if os.getenv("MSPS_TEST_POSTGRES") != "1":
        pytest.skip("Se activa con MSPS_TEST_POSTGRES=1 y una base desechable *_test.")
    if not os.getenv("PGDATABASE", "").endswith("_test"):
        pytest.fail("PGDATABASE debe terminar en _test.")
    esquema = "msps_prueba_" + uuid.uuid4().hex
    with psycopg.connect(autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(esquema)))
        monkeypatch.setenv("MSPS_DB_ENGINE", "postgresql")
        monkeypatch.setenv("PGOPTIONS", "-c search_path=" + esquema)
        monkeypatch.setenv("MSPS_ADMIN_PASSWORD", "solo-prueba-local")
        monkeypatch.setattr(database, "_pool", None)
        try:
            yield
        finally:
            if database._pool:
                database._pool.close()
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(esquema)))


@pytest.fixture(params=["sqlite", "postgresql"])
def motor_sql(request, monkeypatch, tmp_path):
    from app import database

    if request.param == "postgresql":
        request.getfixturevalue("postgres")
    else:
        monkeypatch.setattr(database, "DB_PATH", tmp_path / "motor.db")
        monkeypatch.setattr(database.Database, "_instance", None)
    database.init_db()
    return request.param
