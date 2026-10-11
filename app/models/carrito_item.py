"""
Entidad del carrito (la M de MVC, aunque no toca la base de datos:
el carrito vive en la sesión, no en una tabla).

Principio SOLID aplicado: SRP (Single Responsibility). CarritoItem
solo sabe representar "una máquina con sus horas" y validar sus
propios datos (horas mínimas, tipos). No sabe nada de sesiones,
HTTP ni SQL: eso vive en el repositorio y en el controlador.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class CarritoItem:
    id_maquinaria: int
    horas: int

    def __post_init__(self) -> None:
        self.id_maquinaria = int(self.id_maquinaria)
        self.horas = max(1, int(self.horas))

    def to_dict(self) -> dict:
        return {"id": self.id_maquinaria, "horas": self.horas}

    @staticmethod
    def from_dict(data) -> "CarritoItem":
        if isinstance(data, dict):
            return CarritoItem(id_maquinaria=data["id"], horas=data.get("horas", 1))
        # Compatibilidad con el formato viejo de la sesión (solo IDs sueltos)
        return CarritoItem(id_maquinaria=data, horas=1)