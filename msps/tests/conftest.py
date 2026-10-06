"""Configuración de pruebas.

Por defecto las pruebas usan `mongomock` (MongoDB simulado en memoria, incluido
GridFS), así que corren sin instalar ningún servidor.

Para probar contra un MongoDB REAL, define antes de ejecutar pytest:
    MSPS_TEST_MONGO_URI=mongodb://localhost:27017
Siempre se usa una base con nombre único (msps_test_xxxx) que se borra al final.

La conexión es un Singleton que lee el entorno la primera vez que se crea, por
eso todo se fija ANTES de importar la app.
"""
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_URI_REAL = os.environ.get("MSPS_TEST_MONGO_URI")
_NOMBRE_DB = f"msps_test_{uuid.uuid4().hex[:8]}"
os.environ["MONGODB_DB"] = _NOMBRE_DB

if _URI_REAL:
    os.environ["MONGODB_URI"] = _URI_REAL
else:
    import mongomock
    import mongomock.gridfs
    import pymongo

    mongomock.gridfs.enable_gridfs_integration()
    pymongo.MongoClient = mongomock.MongoClient


def pytest_sessionfinish(session, exitstatus):
    if _URI_REAL:
        from app.documentos.store import MongoConnection

        MongoConnection()._client.drop_database(_NOMBRE_DB)
