
from __future__ import annotations

import os
from typing import Optional

import pymongo
from dotenv import load_dotenv
from pymongo.database import Database

load_dotenv()  

DEFAULT_URI = "mongodb://localhost:27017"
DEFAULT_DB = "msps"
DEFAULT_TIMEOUT_MS = 3000


class MongoConnection:

    _instance: Optional["MongoConnection"] = None

    def __new__(cls) -> "MongoConnection":
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._client = pymongo.MongoClient(
                os.environ.get("MONGODB_URI", DEFAULT_URI),
                serverSelectionTimeoutMS=int(
                    os.environ.get("MONGODB_TIMEOUT_MS", DEFAULT_TIMEOUT_MS)
                ),
            )
            instance._nombre_db = os.environ.get("MONGODB_DB", DEFAULT_DB)
            cls._instance = instance
        return cls._instance

    @property
    def base_datos(self) -> Database:
        return self._client[self._nombre_db]


def get_mongo_database() -> Database:
    """Punto único de acceso a la base MongoDB (Singleton)."""
    return MongoConnection().base_datos
