from __future__ import annotations

import os
import threading
from typing import Optional

from fastapi import Request

from app.models.pagos import ConsultaPagosModel, PagosModel
from app.pagos.wompi import ConfiguracionWompi, Wompi
from app.repositories.pago_repository import PagoRepositorioSQL
from app.documentos.store import get_mongo_database
from app.models.carrito import CarritoModel
from app.models.maquinaria import MaquinariaModel
from app.models.catalogo_fotos import CatalogoFotosModel
from app.models.galeria_maquina import GaleriaMaquinaModel
from app.repositories.carrito_repository import (
    CarritoRepositorioBase,
    CarritoRepositorioSesion,
)
from app.repositories.candado_repository import CandadoMongo
from app.repositories.imagen_maquina_repository import ImagenesGridFS
from app.repositories.imagen_proxy_repository import (
    CACHE_BYTES_POR_DEFECTO,
    CACHE_TTL_POR_DEFECTO,
    ImagenesProxyConCache,
)
from app.repositories.maquina_documentos_repository import MaquinaDocumentosMongo


# El Proxy debe ser UNO por proceso: si se creara uno nuevo en cada petición, su caché
# nacería vacía y nunca serviría de nada.
_proxy_imagenes: Optional[ImagenesProxyConCache] = None
_candado_proxy = threading.Lock()
_documentos = None
_candado_documentos = threading.Lock()


def crear_carrito_repositorio(request: Request) -> CarritoRepositorioBase:
    """Factory Method: centraliza qué implementación de carrito se usa.

    Hoy siempre es CarritoRepositorioSesion. Si el carrito debe
    sobrevivir más allá de la sesión (por ejemplo, guardado en base de
    datos ligado al usuario), esta es la única función que cambia;
    ningún controlador necesita tocarse.
    """
    return CarritoRepositorioSesion(request.session)


def crear_carrito(request: Request) -> CarritoModel:
    """Factory Method: el Modelo del carrito, con su repositorio ya conectado."""
    return CarritoModel(crear_carrito_repositorio(request), MaquinariaModel)


def crear_maquina_documentos_repositorio() -> MaquinaDocumentosMongo:
    """Factory Method: centraliza qué implementación del repositorio de
    documentos (ficha técnica + referencias a imágenes) usa la app.

    Hoy es MongoDB sobre el Singleton MongoConnection. Los Modelos reciben el
    resultado tipado como las interfaces MaquinaDocumentosLector /
    MaquinaDocumentosEscritor.
    """
    global _documentos
    if _documentos is None:
        with _candado_documentos:
            if _documentos is None:
                _documentos = MaquinaDocumentosMongo(get_mongo_database())
    return _documentos


def crear_imagenes_repositorio() -> ImagenesProxyConCache:
    """Factory Method: repositorio de los bytes de las fotos.

    Devuelve el Proxy con caché (una única instancia por proceso) que envuelve a
    ImagenesGridFS. Tamaño y vida de la caché se pueden ajustar con las variables
    MSPS_CACHE_IMAGENES_MB y MSPS_CACHE_IMAGENES_TTL (segundos).
    """
    global _proxy_imagenes
    if _proxy_imagenes is None:
        with _candado_proxy:
            if _proxy_imagenes is None:
                megas = float(os.environ.get("MSPS_CACHE_IMAGENES_MB", CACHE_BYTES_POR_DEFECTO / 1024 / 1024))
                _proxy_imagenes = ImagenesProxyConCache(
                    ImagenesGridFS(get_mongo_database()),
                    max_bytes=int(megas * 1024 * 1024),
                    ttl_segundos=float(os.environ.get("MSPS_CACHE_IMAGENES_TTL", CACHE_TTL_POR_DEFECTO)),
                )
    return _proxy_imagenes


def crear_catalogo_fotos() -> CatalogoFotosModel:
    """Factory Method: el Modelo que entrega portadas, fichas e imagen por categoría."""
    return CatalogoFotosModel(crear_maquina_documentos_repositorio())


def crear_galeria_maquina() -> GaleriaMaquinaModel:
    """Factory Method: el Modelo de la galería de fotos (la usa el administrador)."""
    return GaleriaMaquinaModel(crear_maquina_documentos_repositorio(), crear_imagenes_repositorio())


def crear_candado_repositorio() -> CandadoMongo:
    """Factory Method: candado distribuido (en MongoDB) para el seed."""
    return CandadoMongo(get_mongo_database())


def crear_consulta_pagos() -> ConsultaPagosModel:
    return ConsultaPagosModel(PagoRepositorioSQL())


def crear_pagos() -> PagosModel:
    return PagosModel(PagoRepositorioSQL(), Wompi(ConfiguracionWompi.desde_entorno()))






