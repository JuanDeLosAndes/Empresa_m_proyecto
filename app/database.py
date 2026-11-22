from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("MSPS_DB_PATH", str(BASE_DIR / "msps.db")))
SCHEMA_PATH = BASE_DIR / "schema.sql"
ESQUEMA_POSTGRES = BASE_DIR / "schema_postgres.sql"


ERRORES_INTEGRIDAD = (sqlite3.IntegrityError, psycopg.IntegrityError)
ERRORES_CONEXION = (sqlite3.Error, psycopg.Error)
_pool = None
_pool_lock = threading.Lock()


def motor() -> str:
    elegido = os.environ.get("MSPS_DB_ENGINE", "sqlite").strip().lower()
    if elegido not in {"sqlite", "postgresql"}:
        raise ValueError("MSPS_DB_ENGINE debe ser sqlite o postgresql.")
    return elegido


def _pool_postgres() -> ConnectionPool:
    global _pool
    with _pool_lock:
        if _pool is None:
            for nombre in ("PGHOST", "PGDATABASE", "PGUSER", "PGPASSWORD"):
                if not os.environ.get(nombre):
                    raise RuntimeError(f"Falta configurar {nombre} en la aplicación.")
            if os.environ.get("WEBSITE_SITE_NAME"):
                if os.getenv("PGSSLMODE") != "verify-full" or not os.getenv("PGSSLROOTCERT"):
                    raise RuntimeError("En Azure configura PGSSLMODE=verify-full y PGSSLROOTCERT.")
            pool = ConnectionPool(
                open=False, min_size=0, max_size=5, timeout=12,
                kwargs={"row_factory": dict_row, "connect_timeout": 5},
                check=ConnectionPool.check_connection,
            )
            pool.open()
            _pool = pool
        return _pool


class _SesionPostgres:
    def __init__(self, conexion):
        self._conexion = conexion

    def execute(self, consulta, valores=()):
        # Las consultas de la aplicación usan ? exclusivamente para parámetros.
        if valores:
            return self._conexion.execute(consulta.replace("?", "%s"), valores)
        return self._conexion.execute(consulta)


class Database:
    """Una conexión SQLite por hilo; las transacciones de escritura son independientes."""
    _instance: Optional["Database"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "Database":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._local = threading.local()
                    cls._instance = instance
        return cls._instance

    @property
    def connection(self) -> sqlite3.Connection:
        if not hasattr(self._local, "connection"):
            self._local.connection = abrir_conexion()
        return self._local.connection


def abrir_conexion() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


def get_connection() -> sqlite3.Connection:
    """Compatibilidad con herramientas SQLite. El modelo usa transaccion()."""
    if motor() != "sqlite":
        raise RuntimeError("Para PostgreSQL usa el contexto transaccion().")
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
    """Prepara el esquema del motor elegido y migra las versiones antiguas de SQLite."""
    if motor() == "postgresql":
        if os.getenv("WEBSITE_SITE_NAME") and len(os.getenv("MSPS_SECRET_KEY", "")) < 32:
            raise RuntimeError("Configura MSPS_SECRET_KEY con una clave fija de al menos 32 caracteres.")
        with transaccion(serializar="esquema") as db:
            db.execute(ESQUEMA_POSTGRES.read_text(encoding="utf-8"))
            for rol in ("empresa", "administrador", "persona_natural"):
                db.execute(
                    "INSERT INTO roles(nombre) SELECT CAST(? AS text) WHERE NOT EXISTS "
                    "(SELECT 1 FROM roles WHERE nombre = ?)", (rol, rol),
                )
        return
    preparar_esquema_sqlite(get_connection())


def preparar_esquema_sqlite(conn: sqlite3.Connection) -> None:
    """Aplica el esquema y los cambios históricos a la conexión SQLite indicada."""
    _migrar_esquema_anterior(conn)
    with open(SCHEMA_PATH, "r", encoding="utf-8") as archivo:
        conn.executescript(archivo.read())
    if "ficha_admin" not in _columnas(conn, "maquinarias"):
        conn.execute("ALTER TABLE maquinarias ADD COLUMN ficha_admin TEXT")
    if "disponible" not in _columnas(conn, "maquinarias"):
        conn.execute("ALTER TABLE maquinarias ADD COLUMN disponible INTEGER NOT NULL DEFAULT 1 CHECK(disponible IN (0, 1))")

    if "eliminada" not in _columnas(conn, "maquinarias"):
        conn.execute("ALTER TABLE maquinarias ADD COLUMN eliminada INTEGER NOT NULL DEFAULT 0")
    conn.commit()


@contextmanager
def transaccion(*, serializar: str | None = None):
    """Confirma al salir correctamente y revierte la operación completa si falla."""
    if motor() == "postgresql":
        with _pool_postgres().connection() as conexion:
            db = _SesionPostgres(conexion)
            if serializar:
                db.execute("SELECT pg_advisory_xact_lock(72654, hashtext(?))", (serializar,))
            yield db
        return
    conn = abrir_conexion()
    try:
        with conn:
            if serializar:
                conn.execute("BEGIN IMMEDIATE")
            yield conn
    finally:
        conn.close()
