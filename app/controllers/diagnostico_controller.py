from __future__ import annotations

import time

from fastapi import APIRouter, Depends
from pymongo.errors import PyMongoError

from app.controllers.dependencias import exigir_admin
from app.current_user import SesionActual
from app.database import transaccion
from app.documentos.store import ejecutar_mongo, get_mongo_database

router = APIRouter()


@router.get("/admin/diagnostico")
def diagnostico(_: SesionActual = Depends(exigir_admin)):
    """Solo admin. No devuelve la URI ni las credenciales."""
    inicio = time.perf_counter()
    with transaccion() as db:
        db.execute("SELECT 1").fetchone()
    sqlite_ms = round((time.perf_counter() - inicio) * 1000, 1)
    inicio = time.perf_counter()
    try:
        def consultar():
            base = get_mongo_database()
            base.command("ping")
            return {"documentos_maquinas": base.maquinas.count_documents({}),
                    "fotos": base["fs.files"].count_documents({}),
                    "bloques": base["fs.chunks"].count_documents({})}
        mongo = ejecutar_mongo(consultar)
        mongo.update(ok=True, duracion_ms=round((time.perf_counter() - inicio) * 1000, 1))
    except PyMongoError as error:
        mongo = {"ok": False, "tipo_error": type(error).__name__,
                 "duracion_ms": round((time.perf_counter() - inicio) * 1000, 1),
                 "revisar": "MONGODB_URI, MONGODB_DB, usuario, TLS y acceso de red desde Azure"}
    return {"sqlite": {"ok": True, "duracion_ms": sqlite_ms}, "mongodb": mongo}