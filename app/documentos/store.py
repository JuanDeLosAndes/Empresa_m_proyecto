from __future__ import annotations

import logging
import os
import threading
import time
from typing import Callable, TypeVar

import pymongo
from pymongo.errors import ConfigurationError, ConnectionFailure, ExecutionTimeout, OperationFailure, ServerSelectionTimeoutError

logger = logging.getLogger(__name__)
T = TypeVar("T")


class MongoTemporalmenteNoDisponible(ServerSelectionTimeoutError):
    pass


class MongoConnection:
    """Un cliente y su pool de conexiones por proceso."""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    uri = os.environ.get("MONGODB_URI", "").strip()
                    if not uri:
                        uri = "mongodb://localhost:27017"
                    limite = int(os.environ.get("MONGODB_TIMEOUT_MS", "1500"))
                    instance._client = pymongo.MongoClient(
                        uri, serverSelectionTimeoutMS=limite,
                        connectTimeoutMS=limite, socketTimeoutMS=limite,
                        maxPoolSize=20, minPoolSize=0, appname="MSPS",
                    )
                    instance._nombre_db = os.environ.get("MONGODB_DB", "msps")
                    cls._instance = instance
        return cls._instance

    @property
    def base_datos(self):
        return self._client[self._nombre_db]


class DisponibilidadMongo:
    """Tras un fallo, evita repetir la misma espera en todas las fotos y páginas."""
    def __init__(self, reloj=time.monotonic):
        self._reloj = reloj
        self._reintentar = 0.0
        self._sondeando = False
        self._lock = threading.Lock()

    def ejecutar(self, operacion: Callable[[], T]) -> T:
        with self._lock:
            if self._reloj() < self._reintentar or self._sondeando:
                raise MongoTemporalmenteNoDisponible("MongoDB en espera de reconexión.")
            sondeo = self._reintentar > 0
            if sondeo:
                self._sondeando = True
        try:
            if os.environ.get("WEBSITE_INSTANCE_ID") and not os.environ.get("MONGODB_URI", "").strip():
                raise ConfigurationError("Configura MONGODB_URI en Azure.")
            with pymongo.timeout(int(os.environ.get("MONGODB_TIMEOUT_MS", "1500")) / 1000):
                resultado = operacion()
        except (ConnectionFailure, ExecutionTimeout, OperationFailure, ConfigurationError) as error:
            with self._lock:
                self._reintentar = self._reloj() + float(os.environ.get("MONGODB_REINTENTO_SEGUNDOS", "15"))
            # No escribir la URI, claves ni el texto de la excepción en los logs.
            logger.warning("MongoDB no disponible (%s). Revisa URI, credenciales y acceso de red.", type(error).__name__)
            raise
        else:
            with self._lock:
                self._reintentar = 0.0
            return resultado
        finally:
            if sondeo:
                with self._lock:
                    self._sondeando = False


_disponibilidad = DisponibilidadMongo()


def ejecutar_mongo(operacion: Callable[[], T]) -> T:
    return _disponibilidad.ejecutar(operacion)


def get_mongo_database():
    return MongoConnection().base_datos