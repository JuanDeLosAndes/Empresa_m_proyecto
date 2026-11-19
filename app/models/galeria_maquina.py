
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Protocol

from pymongo.errors import PyMongoError

from app.documentos import galeria as g
from app.documentos.maquina_documento import ImagenMaquina, MaquinaDocumento
from app.models.maquinaria import Maquinaria
from app.documentos.imagen import ImagenBinaria
from app.procesar_imagen import MAX_BYTES, FotoInvalida, procesar_foto


class AlmacenNoDisponible(RuntimeError):
    """MongoDB no respondió: no se hizo ningún cambio (o quedó incompleto y se puede reintentar)."""


@dataclass(frozen=True)
class ResultadoSubida:
    subidas: int
    rechazadas: int


class _Documentos(Protocol):
    def obtener_por_placa(self, placa: str) -> Optional[MaquinaDocumento]: ...
    def listar(self) -> list[MaquinaDocumento]: ...
    def insertar_si_falta(self, documento: MaquinaDocumento) -> bool: ...
    def actualizar_imagenes(self, placa: str, imagenes: list[ImagenMaquina]) -> None: ...


class _Imagenes(Protocol):
    def obtener(self, archivo: str) -> Optional[ImagenBinaria]: ...
    def guardar(self, archivo: str, contenido: bytes, tipo_contenido: str = "image/jpeg") -> bool: ...
    def eliminar(self, archivo: str) -> None: ...


class GaleriaMaquinaModel:
    MAX_FOTOS = g.MAX_FOTOS_POR_MAQUINA
    MAX_BYTES_POR_FOTO = MAX_BYTES

    def __init__(self, documentos: _Documentos, imagenes: _Imagenes) -> None:
        self._documentos = documentos
        self._imagenes = imagenes

    # ---- consultas -----------------------------------------------------------------
    def imagen(self, archivo: str) -> Optional[ImagenBinaria]:
        return self._imagenes.obtener(archivo)

    def fotos_por_placa(self) -> dict[str, int]:
        return {d.placa: len(d.imagenes) for d in self._documentos.listar()}

    def fotos_de(self, maquina: Maquinaria) -> list[ImagenMaquina]:
        documento = self._documentos.obtener_por_placa(maquina.placa)
        return list(documento.imagenes) if documento else []

    def cupos_libres(self, fotos: list[ImagenMaquina]) -> int:
        return max(0, self.MAX_FOTOS - len(fotos))

    # ---- cambios -------------------------------------------------------------------
    def subir(self, maquina: Maquinaria, archivos: Iterable[tuple[str, bytes]]) -> ResultadoSubida:
        """`archivos` = (nombre original, bytes). Cada foto se valida y se reduce a JPEG."""
        try:
            documento = self._documento_o_crear(maquina)
            lista = list(documento.imagenes)
            alt = f"{maquina.marca} {maquina.modelo or ''}".strip()
            subidas = rechazadas = 0
            for nombre, contenido in archivos:
                if len(lista) >= self.MAX_FOTOS:
                    rechazadas += 1
                    continue
                try:
                    jpeg = procesar_foto(contenido)
                except FotoInvalida:
                    rechazadas += 1
                    continue
                nueva = g.foto_nueva(documento.slug, len(lista), alt, nombre)
                self._imagenes.guardar(nueva.archivo, jpeg)  # primero los bytes...
                lista = g.agregar(lista, nueva)
                subidas += 1
            if subidas:
                self._documentos.actualizar_imagenes(maquina.placa, lista)  # ...después la referencia
        except PyMongoError as error:
            raise AlmacenNoDisponible(str(error)) from error
        return ResultadoSubida(subidas=subidas, rechazadas=rechazadas)

    def poner_portada(self, maquina: Maquinaria, archivo: str) -> None:
        try:
            documento = self._documentos.obtener_por_placa(maquina.placa)
            if documento is not None:
                self._documentos.actualizar_imagenes(
                    maquina.placa, g.poner_portada(documento.imagenes, archivo)
                )
        except PyMongoError as error:
            raise AlmacenNoDisponible(str(error)) from error

    def eliminar(self, maquina: Maquinaria, archivo: str) -> None:
        try:
            documento = self._documentos.obtener_por_placa(maquina.placa)
            # Solo se borran fotos que pertenecen a ESTA máquina.
            if documento is not None and any(i.archivo == archivo for i in documento.imagenes):
                self._documentos.actualizar_imagenes(maquina.placa, g.quitar(documento.imagenes, archivo))
                self._imagenes.eliminar(archivo)  # referencia primero, luego los bytes
        except PyMongoError as error:
            raise AlmacenNoDisponible(str(error)) from error

    # ---- interno -------------------------------------------------------------------
    def _documento_o_crear(self, maquina: Maquinaria) -> MaquinaDocumento:
        documento = self._documentos.obtener_por_placa(maquina.placa)
        if documento is None:
            # Máquina que existe en SQL pero aún no tiene documento en Mongo: se crea vacío.
            self._documentos.insertar_si_falta(
                g.documento_minimo(
                    maquina.placa, maquina.marca, maquina.modelo,
                    maquina.nombre_categoria or "", maquina.descripcion, maquina.capacidad,
                )
            )
            documento = self._documentos.obtener_por_placa(maquina.placa)
        if documento is None:
            raise AlmacenNoDisponible("No se pudo leer ni crear el documento de la máquina")
        return documento

