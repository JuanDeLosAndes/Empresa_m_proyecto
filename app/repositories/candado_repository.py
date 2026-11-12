
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone

from pymongo.database import Database
from pymongo.errors import DuplicateKeyError


class Candado(ABC):
    @abstractmethod
    def adquirir(self, nombre: str, segundos: int = 60) -> bool:
        """True si quedó tomado por este proceso; False si otro lo tiene."""

    @abstractmethod
    def liberar(self, nombre: str) -> None: ...


class CandadoMongo(Candado):
    COLECCION = "candados"

    def __init__(self, base_datos: Database) -> None:
        self._col = base_datos[self.COLECCION]

    def adquirir(self, nombre: str, segundos: int = 60) -> bool:
        ahora = datetime.now(timezone.utc)
        try:
            self._col.update_one(
                {"_id": nombre, "vence": {"$lt": ahora}},
                {"$set": {"vence": ahora + timedelta(seconds=segundos)}},
                upsert=True,
            )
            return True
        except DuplicateKeyError:
            return False

    def liberar(self, nombre: str) -> None:
        self._col.delete_one({"_id": nombre})

