"""
Modelo de Maquinaria (la M de MVC).

Encapsula todo el acceso a la tabla `maquinarias`. Los listados
incluyen el nombre de la categoría (JOIN con `categorias`) porque las
vistas de catálogo y detalle lo necesitan para mostrarlo; esto evita
que la plantilla tenga que hacer una segunda consulta o que el
Controlador arme el join a mano.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.database import get_connection


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

    @staticmethod
    def _from_row(row) -> "Maquinaria":
        return Maquinaria(
            id_maquinaria=row["id_maquinaria"],
            marca=row["marca"],
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
        conn = get_connection()
        if categoria:
            filas = conn.execute(
                _SELECT_CON_CATEGORIA + " WHERE c.nombre_categoria = ? ORDER BY m.marca",
                (categoria,),
            ).fetchall()
        else:
            filas = conn.execute(_SELECT_CON_CATEGORIA + " ORDER BY m.marca").fetchall()
        return [Maquinaria._from_row(f) for f in filas]

    @staticmethod
    def obtener_por_id(id_maquinaria: int) -> Optional[Maquinaria]:
        conn = get_connection()
        fila = conn.execute(
            _SELECT_CON_CATEGORIA + " WHERE m.id_maquinaria = ?", (id_maquinaria,)
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
    ) -> Maquinaria:
        conn = get_connection()
        cursor = conn.execute(
            """INSERT INTO maquinarias
                   (marca, descripcion, capacidad, modelo, costo_por_hora, placa, id_categoria)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (marca, descripcion, capacidad, modelo, costo_por_hora, placa, id_categoria),
        )
        conn.commit()
        maquina = MaquinariaModel.obtener_por_id(cursor.lastrowid)
        assert maquina is not None
        return maquina