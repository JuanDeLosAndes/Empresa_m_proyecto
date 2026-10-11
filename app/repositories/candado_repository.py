# ======================================================================
# QUÉ HACE
#   Un 'candado' guardado en MongoDB para que SOLO UN proceso a la vez cargue el
#   catálogo inicial.
# HASTA DÓNDE LLEGA (y qué NO hace)
#   Solo toma y suelta el candado. No sabe qué se está cargando. Existe porque
#   uvicorn --reload y gunicorn arrancan varios procesos a la vez y dos subidas
#   simultáneas pueden dañar fotos.
# ======================================================================
"""
Candado distribuido en MongoDB: asegura que SOLO UN proceso a la vez cargue el
catálogo inicial (documentos y fotos).

Hace falta porque `uvicorn --reload` (y gunicorn con varios workers) arrancan
más de un proceso a la vez, y si dos suben la misma foto simultáneamente
pueden dejarla dañada. El candado vive en la colección `candados`.

Principios SOLID: ISP/DIP, igual que los demás repositorios (la interfaz
`Candado` es lo único que ve el seed).
"""
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
            # Solo coincide si el candado no existe o ya venció (por si un proceso
            # murió sin liberarlo). Si existe y sigue vigente, el upsert intenta
            # insertar un _id repetido y MongoDB lo rechaza: el candado está ocupado.
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

# ======================================================================
# CÓMO LO HACE (en concreto)
#   - adquirir(nombre, segundos=60): update_one({'_id': nombre, 'vence': {'$lt':
#     ahora}}, {'$set': {'vence': ahora + segundos}}, upsert=True). Si el candado
#     existe y sigue vigente, el upsert choca con el _id repetido (DuplicateKeyError)
#     y devuelve False.
#   - Si el proceso murió sin soltarlo, el candado vence solo a los 60 segundos.
#   - liberar(nombre): delete_one({'_id': nombre}).
# USA
#   pymongo (colección `candados`).
# DÓNDE SE LLAMA
#   factories.crear_candado_repositorio, usada solo por seed.py en _sembrar_mongo
#   (adquirir al empezar, liberar en el finally).
# ======================================================================