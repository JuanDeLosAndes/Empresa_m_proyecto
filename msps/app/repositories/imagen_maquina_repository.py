"""
Repositorio de IMÁGENES de máquinas: los bytes de cada foto viven dentro
de MongoDB, en GridFS (colecciones `fs.files` y `fs.chunks`).

GridFS es el mecanismo estándar de MongoDB para guardar archivos: parte
cada foto en bloques y los almacena como documentos. Se usa la identidad
`_id = archivo` (por ejemplo "john-deere-200g-mc770043/01.jpg", la misma
cadena que el documento de la máquina guarda en `imagenes[].archivo`), lo
que enlaza ambos sin tablas intermedias y hace imposible duplicar una
foto aunque varios workers la suban a la vez.

Principios SOLID aplicados: los mismos que en
maquina_documentos_repository.py (ISP con Lector/Escritor separados, DIP,
OCP, SRP, LSP). El controlador que sirve las fotos solo conoce
`ImagenesLector`.
"""
from __future__ import annotations

import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import gridfs
from gridfs.errors import FileExists, NoFile
from pymongo.database import Database
from pymongo.errors import PyMongoError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ImagenBinaria:
    contenido: bytes
    tipo_contenido: str
    sha256: str


class ImagenesLector(ABC):
    @abstractmethod
    def obtener(self, archivo: str) -> Optional[ImagenBinaria]: ...


class ImagenesEscritor(ABC):
    @abstractmethod
    def guardar(self, archivo: str, contenido: bytes, tipo_contenido: str = "image/jpeg") -> bool:
        """Sube o reemplaza una foto. Devuelve True solo si hubo cambios."""


class ImagenesGridFS(ImagenesLector, ImagenesEscritor):
    def __init__(self, base_datos: Database) -> None:
        self._fs = gridfs.GridFS(base_datos)

    def obtener(self, archivo: str) -> Optional[ImagenBinaria]:
        try:
            salida = self._fs.get(archivo)
            meta = salida.metadata or {}
            return ImagenBinaria(
                contenido=salida.read(),
                tipo_contenido=meta.get("tipo_contenido", "image/jpeg"),
                sha256=meta.get("sha256", ""),
            )
        except NoFile:
            return None
        except PyMongoError as error:
            logger.warning("MongoDB no disponible al leer la imagen %s: %s", archivo, error)
            return None

    def guardar(self, archivo: str, contenido: bytes, tipo_contenido: str = "image/jpeg") -> bool:
        huella = hashlib.sha256(contenido).hexdigest()
        try:
            actual = self._fs.get(archivo)
            if (actual.metadata or {}).get("sha256") == huella:
                return False  # ya está idéntica: no se vuelve a subir
            self._fs.delete(archivo)  # cambió: se reemplaza
        except NoFile:
            pass
        try:
            self._fs.put(
                contenido,
                _id=archivo,
                filename=archivo,
                metadata={"sha256": huella, "tipo_contenido": tipo_contenido},
            )
        except FileExists:
            return False  # otro worker la subió en el mismo instante
        return True
