from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ImagenBinaria:
    contenido: bytes
    tipo_contenido: str
    sha256: str


class ImagenesLector(ABC):
    """Devuelve None si no existe y AlmacenNoDisponible ante un fallo de lectura."""

    @abstractmethod
    def obtener(self, archivo: str) -> ImagenBinaria | None: ...


class ImagenesEscritor(ABC):
    @abstractmethod
    def guardar(self, archivo: str, contenido: bytes, tipo_contenido: str = "image/jpeg") -> bool:
        """Devuelve True si creó o reparó el archivo."""

    @abstractmethod
    def eliminar(self, archivo: str) -> None:
        """Borra un archivo. Si está ausente, la operación es idempotente."""


class AlmacenImagenes(ImagenesLector, ImagenesEscritor):
    """Contrato completo para quienes necesitan leer y modificar imágenes."""