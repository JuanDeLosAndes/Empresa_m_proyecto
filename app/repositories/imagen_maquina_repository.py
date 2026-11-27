from __future__ import annotations

import hashlib
import functools
import logging
import math
from typing import Optional

import gridfs
from gridfs.errors import FileExists, GridFSError, NoFile
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.documentos.imagen import AlmacenImagenes, ImagenBinaria, ImagenesLector, ImagenesEscritor
from app.models.almacen import AlmacenNoDisponible
from app.documentos.store import ejecutar_mongo

logger = logging.getLogger(__name__)


def _limite_mongo(metodo):
    @functools.wraps(metodo)
    def envoltura(self, *args, **kwargs):
        try:
            return ejecutar_mongo(lambda: metodo(self, *args, **kwargs))
        except (GridFSError, PyMongoError) as error:
            raise AlmacenNoDisponible("El almacenamiento de imágenes no respondió.") from error
    return envoltura


class ImagenesGridFS(AlmacenImagenes):
    def __init__(self, base_datos: Database) -> None:
        self._fs = gridfs.GridFS(base_datos)
        self._chunks = base_datos["fs.chunks"]

    def obtener(self, archivo: str) -> Optional[ImagenBinaria]:
        try:
            return ejecutar_mongo(lambda: self._leer(archivo))
        except NoFile:
            return None
        except (GridFSError, PyMongoError) as error:
            raise AlmacenNoDisponible("La imagen no pudo recuperarse del almacenamiento.") from error

    def _leer(self, archivo):
        salida = self._fs.get(archivo)
        meta = salida.metadata or {}
        return ImagenBinaria(
            contenido=salida.read(),
            tipo_contenido=meta.get("tipo_contenido", "image/jpeg"),
            sha256=meta.get("sha256", ""),
        )


    def _bloques_completos(self, registro) -> bool:
        """¿Están en fs.chunks todos los bloques que declara el registro?"""
        esperados = math.ceil(registro.length / registro.chunk_size) if registro.length else 0
        return self._chunks.count_documents({"files_id": registro._id}) == esperados

    @_limite_mongo
    def eliminar(self, archivo: str) -> None:
        self._fs.delete(archivo)
        self._chunks.delete_many({"files_id": archivo})  # restos, si los hubiera

    @_limite_mongo
    def guardar(self, archivo: str, contenido: bytes, tipo_contenido: str = "image/jpeg") -> bool:
        huella = hashlib.sha256(contenido).hexdigest()
        try:
            actual = self._fs.get(archivo)
            if (actual.metadata or {}).get("sha256") == huella:
                if self._bloques_completos(actual):
                    return False  # ya está idéntica y completa: no se vuelve a subir
                logger.warning("La imagen %s estaba dañada (faltan bloques); se vuelve a subir.", archivo)
            self._fs.delete(archivo)  # cambió o estaba dañada: se reemplaza
        except NoFile:
            pass
        # Restos de una subida interrumpida (bloques sin registro) bloquearían la nueva subida.
        self._chunks.delete_many({"files_id": archivo})
        try:
            self._fs.put(
                contenido,
                _id=archivo,
                filename=archivo,
                metadata={"sha256": huella, "tipo_contenido": tipo_contenido},
            )
        except (FileExists, DuplicateKeyError):
            logger.warning("Otro proceso subió %s al mismo tiempo; se revisará al reiniciar.", archivo)
            return False
        return True