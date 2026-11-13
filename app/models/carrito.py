
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.models.maquinaria import Maquinaria, MaquinariaModel

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


class CarritoModel:
    def __init__(self, repositorio: "CarritoRepositorioBase") -> None:
        self._repositorio = repositorio

    def contar(self) -> int:
        return self._repositorio.contar()

    def agregar(self, id_maquinaria: int, horas: int) -> None:
        if MaquinariaModel.obtener_por_id(id_maquinaria) is None:
            raise MaquinaNoEncontrada(id_maquinaria)
        self._repositorio.agregar(id_maquinaria, horas)

    def actualizar_horas(self, id_maquinaria: int, horas: int) -> None:
        self._repositorio.actualizar_horas(id_maquinaria, horas)

    def eliminar(self, id_maquinaria: int) -> None:
        self._repositorio.eliminar(id_maquinaria)

    def vaciar(self) -> None:
        self._repositorio.vaciar()

    def resumen(self) -> ResumenCarrito:
        lineas = []
        for item in self._repositorio.leer():
            maquina = MaquinariaModel.obtener_por_id(item.id_maquinaria)
            if maquina:  # si la máquina ya no existe, se omite
                lineas.append(LineaCarrito(maquina=maquina, horas=item.horas))
        return ResumenCarrito(lineas=lineas)

