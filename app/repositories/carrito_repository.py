
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