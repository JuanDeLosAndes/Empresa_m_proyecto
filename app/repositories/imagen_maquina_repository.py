# ======================================================================
# QUÉ HACE
#   Guarda y entrega los bytes de las fotos dentro de MongoDB usando GridFS
#   (colecciones fs.files y fs.chunks).
# HASTA DÓNDE LLEGA (y qué NO hace)
#   Solo sube y lee fotos por su clave `archivo` (por ejemplo
#   'komatsu-pc130/01.jpg'). No decide qué foto se muestra dónde. Se repara solo: si
#   una foto quedó con bloques faltantes, la vuelve a subir.
# ======================================================================
"""
Repositorio de IMÁGENES de máquinas: los bytes de cada foto viven dentro
de MongoDB, en GridFS (colecciones `fs.files` y `fs.chunks`).

GridFS es el mecanismo estándar de MongoDB para guardar archivos: parte
cada foto en bloques (chunks) y los almacena como documentos. Se usa la
identidad `_id = archivo` (por ejemplo "john-deere-200g-mc770043/01.jpg",
la misma cadena que el documento de la máquina guarda en
`imagenes[].archivo`), lo que enlaza ambos sin tablas intermedias.

AUTORREPARACIÓN: una foto puede quedar dañada si dos procesos (p. ej. el
proceso padre y el hijo de `uvicorn --reload`) la suben a la vez: el registro
de `fs.files` existe pero faltan sus bloques en `fs.chunks`, y el navegador
recibe un 404. Por eso `guardar` NO se fía de que el registro exista:
comprueba que los bloques estén completos y, si no, borra los restos y
vuelve a subir la foto.

Principios SOLID aplicados: los mismos que en
maquina_documentos_repository.py (ISP con Lector/Escritor separados, DIP,
OCP, SRP, LSP). El controlador que sirve las fotos solo conoce
`ImagenesLector`.
"""
from __future__ import annotations

import hashlib
import logging
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import gridfs
from gridfs.errors import FileExists, GridFSError, NoFile
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError, PyMongoError

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
        """Sube o repara una foto. Devuelve True solo si hubo cambios."""


class ImagenesGridFS(ImagenesLector, ImagenesEscritor):
    def __init__(self, base_datos: Database) -> None:
        self._fs = gridfs.GridFS(base_datos)
        self._chunks = base_datos["fs.chunks"]

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
        except (GridFSError, PyMongoError) as error:
            logger.warning("No se pudo leer la imagen %s de MongoDB: %s", archivo, error)
            return None

    def _bloques_completos(self, registro) -> bool:
        """¿Están en fs.chunks todos los bloques que declara el registro?"""
        esperados = math.ceil(registro.length / registro.chunk_size) if registro.length else 0
        return self._chunks.count_documents({"files_id": registro._id}) == esperados

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

# ======================================================================
# CÓMO LO HACE (en concreto)
#   - obtener(archivo): self._fs.get(archivo) busca por _id y devuelve
#     ImagenBinaria(bytes, tipo, sha256); si no existe, None.
#   - guardar(archivo, bytes): calcula el sha256. Si ya existe igual y con todos sus
#     bloques, no hace nada. Si cambió o está dañada, la borra, limpia restos en
#     fs.chunks y la sube con put(_id=archivo, filename=archivo, metadata={sha256,
#     tipo_contenido}).
#   - _bloques_completos compara los bloques que hay en fs.chunks con los que declara
#     el registro (longitud / tamaño de bloque).
# USA
#   gridfs y pymongo.
# DÓNDE SE LLAMA
#   factories.crear_imagenes_repositorio, usada por media_controller.py (obtener) y
#   seed.py (guardar).
# ======================================================================
