"""
Repositorio de documentos de máquinas (ficha técnica + referencias a imágenes)
sobre MongoDB: colección `maquinas`, un documento por máquina.

Principios SOLID aplicados:
- ISP (Interface Segregation): lectura y escritura son contratos
  separados. Los controladores públicos solo necesitan leer, así que
  dependen únicamente de `MaquinaDocumentosLector` y no pueden
  modificar nada por accidente; el seed usa además `MaquinaDocumentosEscritor`.
- DIP (Dependency Inversion): controladores y seed dependen de las
  interfaces abstractas, nunca de pymongo. La implementación concreta se
  obtiene con `crear_maquina_documentos_repositorio()` en app/factories.py.
- OCP (Open/Closed): otro motor (o una versión en memoria para pruebas)
  se agrega como otra clase que cumpla los mismos contratos.
- SRP: esta clase solo traduce entre MaquinaDocumento y la colección; no
  construye documentos (Builder), no decide fichas (Factory) y no guarda
  los bytes de las fotos (eso es de imagen_maquina_repository.py).
- LSP: cualquier implementación puede sustituir a otra sin que los
  clientes lo noten.

Tolerancia a fallos: si MongoDB no responde, las LECTURAS registran el
problema y devuelven "sin datos" (el sitio sigue funcionando, mostrando
las máquinas sin galería ni ficha). La ESCRITURA sí propaga el error,
para que el seed no finja que guardó algo.
"""
from __future__ import annotations

import functools
import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Optional

from pymongo.database import Database
from pymongo.errors import DuplicateKeyError, PyMongoError

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


class MaquinaDocumentosEscritor(ABC):
    """Contrato de escritura."""

    @abstractmethod
    def guardar(self, documento: MaquinaDocumento) -> bool:
        """Crea o actualiza (por slug, que no cambia aunque se corrija la
        placa). Devuelve True solo si hubo cambios."""


def _lectura_tolerante(por_defecto: Callable[[], Any]):
    """Decorador: ante un fallo de MongoDB, registra y devuelve un valor vacío."""

    def decorador(metodo):
        @functools.wraps(metodo)
        def envoltura(self, *args, **kwargs):
            try:
                return metodo(self, *args, **kwargs)
            except PyMongoError as error:
                logger.warning("MongoDB no disponible al leer máquinas: %s", error)
                return por_defecto()

        return envoltura

    return decorador


class MaquinaDocumentosMongo(MaquinaDocumentosLector, MaquinaDocumentosEscritor):
    COLECCION = "maquinas"

    def __init__(self, base_datos: Database) -> None:
        self._col = base_datos[self.COLECCION]

    def asegurar_indices(self) -> None:
        """slug es la identidad del documento; placa se consulta en cada detalle."""
        self._col.create_index("slug", unique=True)
        self._col.create_index("placa")

    @_lectura_tolerante(lambda: None)
    def obtener_por_placa(self, placa: str) -> Optional[MaquinaDocumento]:
        fila = self._col.find_one({"placa": placa}, {"_id": 0})
        return MaquinaDocumento.from_document(fila) if fila else None

    @_lectura_tolerante(list)
    def listar(self) -> list[MaquinaDocumento]:
        return [MaquinaDocumento.from_document(f) for f in self._col.find({}, {"_id": 0})]

    @_lectura_tolerante(dict)
    def portadas_por_placa(self) -> dict[str, ImagenMaquina]:
        # Proyección: solo se traen placa e imágenes, no la ficha completa.
        portadas: dict[str, ImagenMaquina] = {}
        for fila in self._col.find({}, {"_id": 0, "placa": 1, "imagenes": 1}):
            for imagen in fila.get("imagenes", []):
                if imagen.get("portada"):
                    portadas[fila["placa"]] = ImagenMaquina.from_document(imagen)
                    break
        return portadas

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
