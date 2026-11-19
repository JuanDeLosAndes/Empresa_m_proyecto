
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.database import transaccion


@dataclass
class Categoria:
    id_categoria: int
    nombre_categoria: str

    @staticmethod
    def _from_row(row) -> "Categoria":
        return Categoria(
            id_categoria=row["id_categoria"],
            nombre_categoria=row["nombre_categoria"],
        )


class CategoriaModel:
    @staticmethod
    def listar() -> list[Categoria]:
        with transaccion() as conn:
            filas = conn.execute(
                "SELECT * FROM categorias ORDER BY nombre_categoria"
            ).fetchall()
            return [Categoria._from_row(f) for f in filas]

    @staticmethod
    def obtener_por_id(id_categoria: int) -> Optional[Categoria]:
        with transaccion() as conn:
            fila = conn.execute(
                "SELECT * FROM categorias WHERE id_categoria = ?", (id_categoria,)
            ).fetchone()
            return Categoria._from_row(fila) if fila else None

    @staticmethod
    def obtener_por_nombre(nombre_categoria: str) -> Optional[Categoria]:
        with transaccion() as conn:
            fila = conn.execute(
                "SELECT * FROM categorias WHERE nombre_categoria = ?", (nombre_categoria,)
            ).fetchone()
            return Categoria._from_row(fila) if fila else None

    @staticmethod
    def crear(nombre_categoria: str) -> Categoria:
        with transaccion() as conn:
            cursor = conn.execute(
                "INSERT INTO categorias (nombre_categoria) VALUES (?) RETURNING *", (nombre_categoria,)
            )
            return Categoria._from_row(cursor.fetchone())
