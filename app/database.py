

from __future__ import annotations

from contextlib import contextmanager
import sqlite3
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "msps.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"


class Database:

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


def _columnas(conn: sqlite3.Connection, tabla: str) -> set[str]:
    return {fila["name"] for fila in conn.execute(f"PRAGMA table_info({tabla})")}


def _migrar_esquema_anterior(conn: sqlite3.Connection) -> None:
 
    if "rol" not in _columnas(conn, "usuarios"):
        return

    conn.commit()
    # Con las llaves foráneas activas, borrar `usuarios` dispararía el
    # ON DELETE CASCADE de alquileres y perderíamos datos.
    conn.execute("PRAGMA foreign_keys = OFF")

    if "id_rol" not in _columnas(conn, "empresas"):
        conn.execute(
            "ALTER TABLE empresas ADD COLUMN id_rol INTEGER NOT NULL DEFAULT 1 REFERENCES roles(id_rol)"
        )

    conn.execute("DROP TABLE IF EXISTS usuarios_anterior")
    conn.execute("CREATE TABLE usuarios_anterior AS SELECT * FROM usuarios")
    conn.execute("DROP TABLE usuarios")
    conn.commit()

    # Crea roles, usuarios (nueva), personas_naturales y administradores.
    with open(SCHEMA_PATH, "r", encoding="utf-8") as archivo:
        conn.executescript(archivo.read())

    conn.execute(
        """INSERT INTO usuarios (id_usuario, nombre, contrasena_hash, id_empresa, id_rol, fecha_registro)
           SELECT a.id_usuario, a.nombre, a.contrasena_hash, a.id_empresa, r.id_rol, a.fecha_registro
           FROM usuarios_anterior a
           JOIN roles r ON r.nombre = CASE a.rol WHEN 'administrador' THEN 'administrador'
                                                 ELSE 'persona_natural' END"""
    )
    conn.execute(
        """INSERT INTO personas_naturales (id_usuario, cedula, correo, telefono)
           SELECT id_usuario, cedula, correo, telefono
           FROM usuarios_anterior WHERE rol <> 'administrador'"""
    )
    conn.execute(
        """INSERT INTO administradores (id_usuario)
           SELECT id_usuario FROM usuarios_anterior WHERE rol = 'administrador'"""
    )
    conn.execute("DROP TABLE usuarios_anterior")
    conn.commit()
    conn.execute("PRAGMA foreign_keys = ON")


def init_db() -> None:
    """Crea las tablas si no existen (schema.sql) y, si encuentra una
    base con el esquema anterior, la migra conservando sus datos."""
    conn = get_connection()
    _migrar_esquema_anterior(conn)
    with open(SCHEMA_PATH, "r", encoding="utf-8") as archivo:
        conn.executescript(archivo.read())
    if "disponible" not in _columnas(conn, "maquinarias"):
        conn.execute("ALTER TABLE maquinarias ADD COLUMN disponible INTEGER NOT NULL DEFAULT 1 CHECK(disponible IN (0, 1))")

    conn.commit()




@contextmanager
def transaccion():
    """Conexión independiente para cada operación de cotización o afiliación."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        with conn:
            yield conn
    finally:
        conn.close()


