"""
Modelo de Categoría (la M de MVC).

Encapsula todo el acceso a la tabla `categorias`. Ningún Controlador
ni Vista debería ejecutar SQL contra esta tabla directamente: siempre
pasan por CategoriaModel.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.database import get_connection


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
        conn = get_connection()
        filas = conn.execute(
            "SELECT * FROM categorias ORDER BY nombre_categoria"
        ).fetchall()
        return [Categoria._from_row(f) for f in filas]

    @staticmethod
    def obtener_por_id(id_categoria: int) -> Optional[Categoria]:
        conn = get_connection()
        fila = conn.execute(
            "SELECT * FROM categorias WHERE id_categoria = ?", (id_categoria,)
        ).fetchone()
        return Categoria._from_row(fila) if fila else None

    @staticmethod
    def obtener_por_nombre(nombre_categoria: str) -> Optional[Categoria]:
        conn = get_connection()
        fila = conn.execute(
            "SELECT * FROM categorias WHERE nombre_categoria = ?", (nombre_categoria,)
        ).fetchone()
        return Categoria._from_row(fila) if fila else None

    @staticmethod
    def crear(nombre_categoria: str) -> Categoria:
        conn = get_connection()
        cursor = conn.execute(
            "INSERT INTO categorias (nombre_categoria) VALUES (?)", (nombre_categoria,)
        )
        conn.commit()
        return Categoria(id_categoria=cursor.lastrowid, nombre_categoria=nombre_categoria)