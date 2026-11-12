
from __future__ import annotations
from abc import ABC, abstractmethod

from fastapi import Request

from app.models.carrito_item import CarritoItem


class CarritoRepositorioBase(ABC):

    @abstractmethod
    def leer(self) -> list[CarritoItem]:
        ...

    @abstractmethod
    def guardar(self, items: list[CarritoItem]) -> None:
        ...

    def agregar(self, id_maquinaria: int, horas: int) -> None:
        items = self.leer()
        for item in items:
            if item.id_maquinaria == int(id_maquinaria):
                item.horas = max(1, int(horas))
                break
        else:
            items.append(CarritoItem(id_maquinaria, horas))
        self.guardar(items)

    def actualizar_horas(self, id_maquinaria: int, horas: int) -> None:
        items = self.leer()
        for item in items:
            if item.id_maquinaria == int(id_maquinaria):
                item.horas = max(1, int(horas))
        self.guardar(items)

    def eliminar(self, id_maquinaria: int) -> None:
        items = [i for i in self.leer() if i.id_maquinaria != int(id_maquinaria)]
        self.guardar(items)

    def vaciar(self) -> None:
        self.guardar([])

    def contar(self) -> int:
        return len(self.leer())


class CarritoRepositorioSesion(CarritoRepositorioBase):
    """Guarda el carrito en request.session['carrito']."""

    CLAVE_SESION = "carrito"

    def __init__(self, request: Request):
        self._request = request

    def leer(self) -> list[CarritoItem]:
        crudos = self._request.session.get(self.CLAVE_SESION, [])
        return [CarritoItem.from_dict(item) for item in crudos]

    def guardar(self, items: list[CarritoItem]) -> None:
        # Se reasigna la lista completa para que Starlette detecte el cambio
        self._request.session[self.CLAVE_SESION] = [item.to_dict() for item in items]