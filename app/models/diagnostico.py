import sqlite3
import time
from contextlib import closing
from functools import lru_cache

from pymongo.errors import PyMongoError

from app.database import ERRORES_CONEXION, SCHEMA_PATH, motor, transaccion
from app.documentos.store import ejecutar_mongo, get_mongo_database


def _columnas_sqlite(db):
    return db.execute(
        """SELECT s.name AS tabla, c.name AS campo
           FROM sqlite_master s JOIN pragma_table_info(s.name) c
           WHERE s.type = 'table' AND s.name NOT LIKE 'sqlite_%'"""
    ).fetchall()


@lru_cache(maxsize=1)
def campos_del_proyecto() -> frozenset[tuple[str, str]]:
    with closing(sqlite3.connect(":memory:")) as referencia:
        referencia.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        return frozenset(_columnas_sqlite(referencia))


def estado_relacional():
    nombre = motor()
    inicio = time.perf_counter()
    try:
        with transaccion() as db:
            if nombre == "postgresql":
                filas = db.execute(
                    """SELECT table_name AS tabla, column_name AS campo
                       FROM information_schema.columns WHERE table_schema = current_schema()"""
                ).fetchall()
            else:
                filas = _columnas_sqlite(db)
        encontrados = {(f["tabla"], f["campo"]) for f in filas}
        esperados = campos_del_proyecto()
        presentes = esperados.intersection(encontrados)
        faltantes = sorted(f"{t}.{c}" for t, c in esperados - encontrados)
        estado = {"ok": not faltantes, "tablas": len({t for t, _ in presentes}),
                  "campos": len(presentes), "faltantes": faltantes}
    except ERRORES_CONEXION as error:
        estado = {"ok": False, "tipo_error": type(error).__name__}
    return {**estado, "motor": nombre, "duracion_ms": round((time.perf_counter() - inicio) * 1000, 1)}


def _conteo_mongo():
    base = get_mongo_database()
    base.command("ping")
    return {"documentos_maquinas": base.maquinas.count_documents({}),
            "fotos": base["fs.files"].count_documents({}),
            "bloques": base["fs.chunks"].count_documents({})}


def estado_almacenes():
    relacional = estado_relacional()
    inicio = time.perf_counter()
    try:
        mongo = {"ok": True, **ejecutar_mongo(_conteo_mongo)}
    except PyMongoError as error:
        mongo = {"ok": False, "tipo_error": type(error).__name__,
                 "revisar": "MONGODB_URI, MONGODB_DB, usuario, TLS y acceso de red desde Azure"}
    mongo["duracion_ms"] = round((time.perf_counter() - inicio) * 1000, 1)
    respuesta = {"relacional": relacional, "mongodb": mongo}
    if relacional["motor"] == "sqlite":
        respuesta["sqlite"] = relacional  # Contrato de la versión anterior.
    return respuesta