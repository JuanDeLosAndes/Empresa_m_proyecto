
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
