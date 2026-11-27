from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Callable, Optional

from app.documentos.imagen import (
    AlmacenImagenes,
    ImagenBinaria,
)

CACHE_BYTES_POR_DEFECTO = 32 * 1024 * 1024  # 32 MB: sobra para las ~22 fotos (~6 MB)
CACHE_TTL_POR_DEFECTO = 300.0  # segundos que una foto puede vivir en memoria


class ImagenesProxyConCache(AlmacenImagenes):
    """Proxy (patrón estructural): misma interfaz que ImagenesGridFS, pero con caché LRU."""

    def __init__(
        self,
        real: AlmacenImagenes,
        max_bytes: int = CACHE_BYTES_POR_DEFECTO,
        ttl_segundos: float = CACHE_TTL_POR_DEFECTO,
        reloj: Callable[[], float] = time.monotonic,
    ) -> None:
        self._real = real
        self._max_bytes = max_bytes
        self._ttl = ttl_segundos
        self._reloj = reloj
        self._cache: OrderedDict[str, tuple[ImagenBinaria, float]] = OrderedDict()
        self._bytes = 0
        # Sube con cada escritura/borrado: evita guardar en caché una lectura vieja
        # que terminó justo después de que otro hilo cambió la foto.
        self._version = 0
        self._candado = threading.Lock()  # FastAPI atiende rutas síncronas en varios hilos

    @property
    def bytes_en_cache(self) -> int:
        return self._bytes

    def __len__(self) -> int:
        return len(self._cache)

    def obtener(self, archivo: str) -> Optional[ImagenBinaria]:
        with self._candado:
            entrada = self._cache.get(archivo)
            if entrada is not None:
                imagen, vence = entrada
                if self._reloj() < vence:
                    self._cache.move_to_end(archivo)  # la usada recientemente se queda
                    return imagen
                self._sacar(archivo)  # venció: se vuelve a pedir a MongoDB
            version = self._version
        imagen = self._real.obtener(archivo)  # fuera del candado: no frena a otros hilos
        if imagen is not None:
            with self._candado:
                if version == self._version:
                    self._meter(archivo, imagen)
        return imagen

    def guardar(self, archivo: str, contenido: bytes, tipo_contenido: str = "image/jpeg") -> bool:
        try:
            return self._real.guardar(archivo, contenido, tipo_contenido)
        finally:
            self._invalidar(archivo)

    def eliminar(self, archivo: str) -> None:
        try:
            self._real.eliminar(archivo)
        finally:
            self._invalidar(archivo)

    def limpiar(self) -> None:
        with self._candado:
            self._version += 1
            self._cache.clear()
            self._bytes = 0

    # --- uso interno (siempre con el candado tomado, salvo _invalidar) ---------------
    def _invalidar(self, archivo: str) -> None:
        with self._candado:
            self._version += 1
            self._sacar(archivo)

    def _sacar(self, archivo: str) -> None:
        entrada = self._cache.pop(archivo, None)
        if entrada is not None:
            self._bytes -= len(entrada[0].contenido)

    def _meter(self, archivo: str, imagen: ImagenBinaria) -> None:
        if len(imagen.contenido) > self._max_bytes:
            return  # una sola foto más grande que toda la caché: no se guarda
        self._sacar(archivo)
        self._cache[archivo] = (imagen, self._reloj() + self._ttl)
        self._bytes += len(imagen.contenido)
        while self._bytes > self._max_bytes:  # expulsa las menos usadas
            antigua, (viejo, _) = next(iter(self._cache.items()))
            del self._cache[antigua]
            self._bytes -= len(viejo.contenido)