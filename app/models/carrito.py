from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from app.models.carrito_item import CarritoItem
from app.models.maquinaria import Maquinaria

if TYPE_CHECKING:  # solo para los tipos; evita importaciones circulares en tiempo de ejecución
    from app.repositories.carrito_repository import CarritoRepositorioBase

TASA_IVA = 0.19


class MaquinaNoEncontrada(LookupError):
    """La máquina que se quiso agregar no existe."""


@dataclass(frozen=True)
class LineaCarrito:
    maquina: Maquinaria
    horas: int

    @property
    def total(self) -> float:
        return (self.maquina.costo_por_hora or 0) * self.horas


@dataclass(frozen=True)
class ResumenCarrito:
    lineas: list[LineaCarrito]
    tasa_iva: float = TASA_IVA

    @property
    def subtotal(self) -> float:
        return sum(linea.total for linea in self.lineas)

    @property
    def iva(self) -> float:
        return self.subtotal * self.tasa_iva

    @property
    def total(self) -> float:
        return self.subtotal + self.iva


class ConsultaMaquinaria(Protocol):
    def obtener_por_id(self, id_maquinaria: int) -> Maquinaria | None: ...


class RequiereCotizacion(ValueError):
    pass


class MaquinaNoDisponible(ValueError):
    pass


class CarritoModel:
    def __init__(self, repositorio: "CarritoRepositorioBase", maquinas: ConsultaMaquinaria):
        self._repositorio = repositorio
        self._maquinas = maquinas

    def contar(self) -> int:
        return len(self.resumen().lineas)

    def agregar(self, id_maquinaria: int, horas: int) -> None:
        maquina = self._maquinas.obtener_por_id(id_maquinaria)
        if maquina is None:
            raise MaquinaNoEncontrada(id_maquinaria)
        if not maquina.disponible:
            raise MaquinaNoDisponible("Esta máquina no está disponible")
        if (maquina.costo_por_hora or 0) <= 0:
            raise RequiereCotizacion("Esta máquina requiere cotización")
        items = self._repositorio.leer()
        nuevo = CarritoItem(id_maquinaria, horas)
        for pos, item in enumerate(items):
            if item.id_maquinaria == id_maquinaria:
                items[pos] = nuevo
                break
        else:
            items.append(nuevo)
        self._repositorio.guardar(items)

    def actualizar_horas(self, id_maquinaria: int, horas: int) -> None:
        if not any(i.id_maquinaria == id_maquinaria for i in self._repositorio.leer()):
            raise MaquinaNoEncontrada(id_maquinaria)
        self.agregar(id_maquinaria, horas)

    def eliminar(self, id_maquinaria: int) -> None:
        self._repositorio.guardar([i for i in self._repositorio.leer() if i.id_maquinaria != id_maquinaria])

    def vaciar(self) -> None:
        self._repositorio.guardar([])

    def resumen(self) -> ResumenCarrito:
        lineas = []
        for item in self._repositorio.leer():
            maquina = self._maquinas.obtener_por_id(item.id_maquinaria)
            if maquina and maquina.disponible and (maquina.costo_por_hora or 0) > 0:
                lineas.append(LineaCarrito(maquina, item.horas))
        return ResumenCarrito(lineas)

