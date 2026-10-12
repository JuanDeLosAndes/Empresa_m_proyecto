"""Reglas puras de la galería de una máquina (sin base de datos).

- La portada siempre es la primera foto y solo hay una.
- `orden` se renumera 1..N tras cada cambio.
- Cada foto nueva recibe un nombre único (`slug/<id>.jpg`): así nunca se
  pisa una foto vieja y el navegador no muestra una versión en caché.
"""
from __future__ import annotations

import uuid
from dataclasses import replace
from typing import Optional

from app.documentos.fichas import FichaTecnicaFactory
from app.documentos.maquina_documento import ImagenMaquina, MaquinaDocumento, slugify

MAX_FOTOS_POR_MAQUINA = 12


def nuevo_nombre_archivo(slug: str) -> str:
    return f"{slug}/{uuid.uuid4().hex[:12]}.jpg"


def normalizar(imagenes: list[ImagenMaquina]) -> list[ImagenMaquina]:
    """Una sola portada, primera, y `orden` consecutivo."""
    if not imagenes:
        return []
    portada = next((i.archivo for i in imagenes if i.portada), imagenes[0].archivo)
    ordenadas = sorted(imagenes, key=lambda i: i.archivo != portada)  # estable
    return [replace(i, orden=n, portada=(i.archivo == portada)) for n, i in enumerate(ordenadas, 1)]


def agregar(imagenes: list[ImagenMaquina], nueva: ImagenMaquina) -> list[ImagenMaquina]:
    return normalizar([*imagenes, replace(nueva, portada=not imagenes)])


def quitar(imagenes: list[ImagenMaquina], archivo: str) -> list[ImagenMaquina]:
    return normalizar([i for i in imagenes if i.archivo != archivo])


def poner_portada(imagenes: list[ImagenMaquina], archivo: str) -> list[ImagenMaquina]:
    if not any(i.archivo == archivo for i in imagenes):
        return imagenes
    return normalizar([replace(i, portada=(i.archivo == archivo)) for i in imagenes])


def foto_nueva(slug: str, n_actual: int, alt: str, origen: str) -> ImagenMaquina:
    return ImagenMaquina(
        archivo=nuevo_nombre_archivo(slug),
        orden=n_actual + 1,
        portada=False,
        alt=alt,
        vista=f"Foto {n_actual + 1}",
        origen=origen[:120],
    )


def documento_minimo(placa: str, marca: str, modelo: Optional[str], categoria: str,
                     descripcion: str, capacidad: Optional[str]) -> MaquinaDocumento:
    """Documento para una máquina que existe en SQL pero aún no tiene ficha en Mongo."""
    return MaquinaDocumento(
        placa=placa,
        slug=slugify(f"{marca} {modelo or ''} {placa}"),
        marca=marca,
        modelo=modelo,
        categoria=categoria,
        descripcion=descripcion or "",
        capacidad=capacidad,
        ficha=FichaTecnicaFactory.crear("generica"),
        imagenes=[],
    )