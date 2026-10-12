"""Procesa una foto subida por el administrador antes de guardarla en MongoDB.

Es la misma receta de tools/importar_imagenes.py: corrige la rotación del
celular, reduce a 1400 px, convierte a JPEG progresivo y NO escribe metadatos
(así se pierde el GPS de la foto).
"""
from __future__ import annotations

import io

from PIL import Image, ImageOps, UnidentifiedImageError

LADO_MAXIMO = 1400
CALIDAD_JPEG = 82
MAX_BYTES = 10 * 1024 * 1024  # 10 MB por foto subida
MAX_PIXELES = 60_000_000  # protege de "bombas de descompresión"
FORMATOS_ACEPTADOS = {"JPEG", "PNG", "WEBP"}

Image.MAX_IMAGE_PIXELS = MAX_PIXELES


class FotoInvalida(ValueError):
    """La foto no se puede aceptar (el mensaje se le puede mostrar al admin)."""


def procesar_foto(contenido: bytes) -> bytes:
    if not contenido:
        raise FotoInvalida("El archivo está vacío.")
    if len(contenido) > MAX_BYTES:
        raise FotoInvalida("La foto pesa más de 10 MB.")
    try:
        with Image.open(io.BytesIO(contenido)) as img:
            if img.format not in FORMATOS_ACEPTADOS:
                raise FotoInvalida("Formato no permitido: usa JPG, PNG o WEBP.")
            img = ImageOps.exif_transpose(img).convert("RGB")
            img.thumbnail((LADO_MAXIMO, LADO_MAXIMO), Image.LANCZOS)
            salida = io.BytesIO()
            img.save(salida, "JPEG", quality=CALIDAD_JPEG, optimize=True, progressive=True)
            return salida.getvalue()
    except FotoInvalida:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise FotoInvalida("No es una imagen válida.") from None