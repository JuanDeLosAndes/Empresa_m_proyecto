from __future__ import annotations

import math
import json
from dataclasses import dataclass
from typing import Optional

from app.database import ERRORES_INTEGRIDAD, transaccion


@dataclass
class Maquinaria:
    id_maquinaria: int
    marca: str
    descripcion: Optional[str]
    capacidad: Optional[str]
    modelo: Optional[str]
    costo_por_hora: float
    placa: str
    id_categoria: int
    nombre_categoria: Optional[str] = None
    disponible: bool = True

    ficha_tecnica: dict[str, str] | None = None

    @property
    def tiene_tarifa(self) -> bool:
        return self.costo_por_hora > 0

    @property
    def permite_alquiler_directo(self) -> bool:
        return self.disponible and self.tiene_tarifa

    @staticmethod
    def _from_row(row) -> "Maquinaria":
        return Maquinaria(
            id_maquinaria=row["id_maquinaria"],
            marca=row["marca"],
            ficha_tecnica=json.loads(row["ficha_admin"]) if row["ficha_admin"] else None,
            disponible=bool(row["disponible"]) if "disponible" in row.keys() else True,
            descripcion=row["descripcion"],
            capacidad=row["capacidad"],
            modelo=row["modelo"],
            costo_por_hora=row["costo_por_hora"],
            placa=row["placa"],
            id_categoria=row["id_categoria"],
            nombre_categoria=row["nombre_categoria"] if "nombre_categoria" in row.keys() else None,
        )


_SELECT_CON_CATEGORIA = """
    SELECT m.*, c.nombre_categoria
    FROM maquinarias m
    JOIN categorias c ON c.id_categoria = m.id_categoria
"""


class MaquinariaModel:
    @staticmethod
    def listar(categoria: Optional[str] = None) -> list[Maquinaria]:
        with transaccion() as conn:
            if categoria:
                filas = conn.execute(
                    _SELECT_CON_CATEGORIA + " WHERE m.eliminada = 0 AND c.nombre_categoria = ? ORDER BY m.marca",
                    (categoria,),
                ).fetchall()
            else:
                filas = conn.execute(_SELECT_CON_CATEGORIA + " WHERE m.eliminada = 0 ORDER BY m.marca").fetchall()
            return [Maquinaria._from_row(f) for f in filas]

    @staticmethod
    def obtener_por_id(id_maquinaria: int) -> Optional[Maquinaria]:
        with transaccion() as conn:
            fila = conn.execute(
                _SELECT_CON_CATEGORIA + " WHERE m.eliminada = 0 AND m.id_maquinaria = ?", (id_maquinaria,)
            ).fetchone()
            return Maquinaria._from_row(fila) if fila else None

    @staticmethod
    def crear(
        marca: str,
        costo_por_hora: float,
        placa: str,
        id_categoria: int,
        descripcion: Optional[str] = None,
        capacidad: Optional[str] = None,
        modelo: Optional[str] = None,
        disponible: bool = True,
        ficha_tecnica: dict[str, str] | None = None,
    ) -> Maquinaria:
        validar_tarifa(costo_por_hora)
        with transaccion() as conn:
            if not conn.execute("SELECT 1 FROM categorias WHERE id_categoria = ?", (id_categoria,)).fetchone():
                raise ValueError("Categoría no encontrada")
            try:
                cursor = conn.execute(
                    """INSERT INTO maquinarias
                       (marca, descripcion, capacidad, modelo, costo_por_hora, placa, id_categoria, disponible, ficha_admin)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id_maquinaria""",
                    (marca, descripcion, capacidad, modelo, costo_por_hora, placa, id_categoria, int(disponible),
                     json.dumps(ficha_tecnica, ensure_ascii=False) if ficha_tecnica else None),
                )
            except ERRORES_INTEGRIDAD as error:
                raise ValueError("Ya existe una máquina con esa placa") from error
            id_maquinaria = cursor.fetchone()["id_maquinaria"]
            fila = conn.execute(_SELECT_CON_CATEGORIA + " WHERE m.id_maquinaria = ?", (id_maquinaria,)).fetchone()
            return Maquinaria._from_row(fila)

    @staticmethod
    def actualizar(id_maquinaria: int, costo_por_hora: float, capacidad: str,
                   descripcion: str, disponible: bool, ficha_tecnica: dict[str, str] | None = None) -> Maquinaria:
        validar_tarifa(costo_por_hora)
        with transaccion() as conn:
            resultado = conn.execute(
                """UPDATE maquinarias SET costo_por_hora = ?, capacidad = ?, descripcion = ?, disponible = ?,
                          ficha_admin = COALESCE(?, ficha_admin)
                   WHERE id_maquinaria = ? AND eliminada = 0""",
                (costo_por_hora, capacidad, descripcion, int(disponible), json.dumps(ficha_tecnica, ensure_ascii=False) if ficha_tecnica else None, id_maquinaria),
            )
            if not resultado.rowcount:
                raise LookupError("Máquina no encontrada")
            fila = conn.execute(_SELECT_CON_CATEGORIA + " WHERE m.eliminada = 0 AND m.id_maquinaria = ?", (id_maquinaria,)).fetchone()
            return Maquinaria._from_row(fila)


    @staticmethod
    def eliminar(id_maquinaria: int) -> None:
        with transaccion() as conn:
            resultado = conn.execute(
                "UPDATE maquinarias SET eliminada = 1, disponible = 0 WHERE id_maquinaria = ? AND eliminada = 0",
                (id_maquinaria,),
            )
            if not resultado.rowcount:
                raise LookupError("Máquina no encontrada")


def validar_tarifa(valor: float) -> None:
    if not math.isfinite(valor) or valor < 0:
        raise ValueError("El precio debe ser un número mayor o igual a cero")