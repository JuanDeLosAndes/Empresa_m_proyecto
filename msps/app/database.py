"""
Capa de acceso a la base de datos de MSPS.

Patrón creacional aplicado: SINGLETON (igual que TemplateEngine en
templating.py). Centraliza la única conexión sqlite3 de la app para
que todos los Modelos (la M de MVC) entren por el mismo punto en vez
de que cada modelo o controlador abra conexiones por su cuenta.

Ningún Controlador ni Vista debería importar `sqlite3` directamente:
solo los archivos de app/models/ hablan con la base de datos, y todos
pasan por `get_connection()`.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "msps.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"


class Database:
    """Envoltorio Singleton alrededor de la conexión sqlite3."""

    _instance: Optional["Database"] = None

    def __new__(cls) -> "Database":
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._connection = sqlite3.connect(
                DB_PATH,
                check_same_thread=False,
            )
            instance._connection.row_factory = sqlite3.Row
            instance._connection.execute("PRAGMA foreign_keys = ON")
            cls._instance = instance
        return cls._instance

    @property
    def connection(self) -> sqlite3.Connection:
        return self._connection


def get_connection() -> sqlite3.Connection:
    """Punto único de acceso a la conexión (Singleton)."""
    return Database().connection


def init_db() -> None:
    """Crea las tablas si no existen, ejecutando schema.sql."""
    conn = get_connection()
    with open(SCHEMA_PATH, "r", encoding="utf-8") as archivo:
        conn.executescript(archivo.read())
    conn.commit()