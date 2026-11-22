from dataclasses import dataclass


@dataclass(frozen=True)
class ImagenBinaria:
    contenido: bytes
    tipo_contenido: str
    sha256: str