"""
Conexión a MongoDB (base de datos NO relacional) de MSPS.

Patrón creacional aplicado: SINGLETON (igual que Database en
app/database.py y TemplateEngine en app/templating.py). Un MongoClient
ya administra internamente un pool de conexiones y está pensado para
crearse UNA vez por proceso; el Singleton garantiza que ningún módulo
abra clientes propios.

Configuración (variables de entorno o archivo .env):
    MONGODB_URI   cadena de conexión.  Por defecto: mongodb://localhost:27017
                  (MongoDB Atlas usa una URI "mongodb+srv://...")
    MONGODB_DB    nombre de la base.   Por defecto: msps
    MONGODB_TIMEOUT_MS  espera máxima para encontrar el servidor (3000).

Principio SOLID (DIP): el resto de la app NO importa pymongo para
conectarse; recibe una `Database` ya construida a través de
app/factories.py. Solo los repositorios de app/repositories/ la usan.
"""
from __future__ import annotations

import os
from typing import Optional

import pymongo
from dotenv import load_dotenv
from pymongo.database import Database

load_dotenv()  # lee msps/.env si existe; las variables reales del entorno mandan

DEFAULT_URI = "mongodb://localhost:27017"
DEFAULT_DB = "msps"
DEFAULT_TIMEOUT_MS = 3000


class MongoConnection:
    """Envoltorio Singleton alrededor del cliente de MongoDB."""

    _instance: Optional["MongoConnection"] = None

    def __new__(cls) -> "MongoConnection":
        if cls._instance is None:
            instance = super().__new__(cls)
            # pymongo.MongoClient se resuelve en tiempo de ejecución (no con
            # "from pymongo import MongoClient") para poder sustituirlo en pruebas.
            # MongoClient es perezoso: no se conecta hasta la primera operación.
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
