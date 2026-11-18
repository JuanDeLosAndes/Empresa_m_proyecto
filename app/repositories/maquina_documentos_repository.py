from __future__ import annotations

import functools
import logging
import copy
import os
import threading
import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Optional

from pymongo.database import Database
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.documentos.store import ejecutar_mongo
from app.documentos.maquina_documento import ImagenMaquina, MaquinaDocumento

logger = logging.getLogger(__name__)


class MaquinaDocumentosLector(ABC):
    """Contrato de solo lectura."""

    @abstractmethod
    def obtener_por_placa(self, placa: str) -> Optional[MaquinaDocumento]: ...

    @abstractmethod
    def listar(self) -> list[MaquinaDocumento]: ...

    @abstractmethod
    def portadas_por_placa(self) -> dict[str, ImagenMaquina]: ...

    @abstractmethod
    def portadas_por_categoria(self) -> dict[str, ImagenMaquina]:
        """Una foto de portada de alguna máquina de cada categoría."""


class MaquinaDocumentosEscritor(ABC):
    """Contrato de escritura."""

    @abstractmethod
    def guardar(self, documento: MaquinaDocumento) -> bool:
        """Crea o actualiza (por slug, que no cambia aunque se corrija la
        placa). Devuelve True solo si hubo cambios."""

    @abstractmethod
    def insertar_si_falta(self, documento: MaquinaDocumento) -> bool:
        """Crea el documento solo si no existe (nunca pisa uno ya editado).
        Devuelve True si lo creó."""

    @abstractmethod
    def actualizar_imagenes(self, placa: str, imagenes: list[ImagenMaquina]) -> None:
        """Reemplaza únicamente la lista de fotos del documento."""


def _lectura_tolerante(por_defecto: Callable[[], Any]):
    """Decorador: ante un fallo de MongoDB, registra y devuelve un valor vacío."""

    def decorador(metodo):
        @functools.wraps(metodo)
        def envoltura(self, *args, **kwargs):
            try:
                return metodo(self, *args, **kwargs)
            except PyMongoError as error:
                logger.debug("Lectura omitida: %s", type(error).__name__)
                return por_defecto()

        return envoltura

    return decorador


def _escritura_mongo(metodo):
    @functools.wraps(metodo)
    def envoltura(self, *args, **kwargs):
        try:
            return ejecutar_mongo(lambda: metodo(self, *args, **kwargs))
        finally:
            with self._lock:
                self._cache.clear()
    return envoltura


class MaquinaDocumentosMongo(MaquinaDocumentosLector, MaquinaDocumentosEscritor):
    COLECCION = "maquinas"

    def __init__(self, base_datos: Database) -> None:
        self._col = base_datos[self.COLECCION]
        self._cache = {}
        self._lock = threading.RLock()
        self._ttl = float(os.environ.get("MSPS_CACHE_CATALOGO_TTL", "30"))

    def _recordar(self, clave, consulta):
        with self._lock:
            entrada = self._cache.get(clave)
            if entrada and entrada[0] > time.monotonic():
                return copy.deepcopy(entrada[1])
            resultado = ejecutar_mongo(consulta)
            if len(self._cache) >= 256:
                self._cache.clear()
            self._cache[clave] = (time.monotonic() + self._ttl, resultado)
            return copy.deepcopy(resultado)

    def _portadas(self):
        return self._recordar("portadas", lambda: list(self._col.find(
            {}, {"_id": 0, "placa": 1, "slug": 1, "identidad.categoria": 1, "imagenes": 1}
        )))

    @_escritura_mongo
    def asegurar_indices(self) -> None:
        """slug es la identidad del documento; placa se consulta en cada detalle."""
        self._col.create_index("slug", unique=True)
        self._col.create_index("placa")

    @_lectura_tolerante(lambda: None)
    def obtener_por_placa(self, placa: str) -> Optional[MaquinaDocumento]:
        fila = self._recordar(("ficha", placa), lambda: self._col.find_one({"placa": placa}, {"_id": 0}))
        return MaquinaDocumento.from_document(fila) if fila else None

    @_lectura_tolerante(list)
    def listar(self) -> list[MaquinaDocumento]:
        return ejecutar_mongo(lambda: [MaquinaDocumento.from_document(f) for f in self._col.find({}, {"_id": 0})])

    @_lectura_tolerante(dict)
    def portadas_por_placa(self) -> dict[str, ImagenMaquina]:
        # Proyección: solo se traen placa e imágenes, no la ficha completa.
        portadas: dict[str, ImagenMaquina] = {}
        for fila in self._portadas():
            for imagen in fila.get("imagenes", []):
                if imagen.get("portada"):
                    portadas[fila["placa"]] = ImagenMaquina.from_document(imagen)
                    break
        return portadas

    @_lectura_tolerante(dict)
    def portadas_por_categoria(self) -> dict[str, ImagenMaquina]:
        portadas: dict[str, ImagenMaquina] = {}
        filas = self._portadas()
        for fila in sorted(filas, key=lambda f: f["slug"]):  # orden fijo: siempre la misma foto
            categoria = fila["identidad"]["categoria"]
            if categoria in portadas:
                continue
            for imagen in fila.get("imagenes", []):
                if imagen.get("portada"):
                    portadas[categoria] = ImagenMaquina.from_document(imagen)
                    break
        return portadas

    @_escritura_mongo
    def insertar_si_falta(self, documento: MaquinaDocumento) -> bool:
        if self._col.find_one({"$or": [{"slug": documento.slug}, {"placa": documento.placa}]}, {"_id": 1}):
            return False
        try:
            self._col.insert_one(documento.to_document())
        except DuplicateKeyError:
            return False  # otro worker lo creó justo antes
        return True

    @_escritura_mongo
    def actualizar_imagenes(self, placa: str, imagenes: list[ImagenMaquina]) -> None:
        self._col.update_one({"placa": placa}, {"$set": {"imagenes": [i.to_document() for i in imagenes]}})

    @_escritura_mongo
    def guardar(self, documento: MaquinaDocumento) -> bool:
        nuevo = documento.to_document()
        existente = self._col.find_one({"slug": documento.slug}, {"_id": 0})
        # Idempotente: si no cambió nada, no se escribe. Así el arranque de
        # cada uno de los 4 workers de gunicorn no repite escrituras.
        if existente == nuevo:
            return False
        try:
            self._col.replace_one({"slug": documento.slug}, nuevo, upsert=True)
        except DuplicateKeyError:
            # Otro worker lo insertó en el mismo instante: se reintenta como reemplazo.
            self._col.replace_one({"slug": documento.slug}, nuevo)
        return True
