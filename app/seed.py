from __future__ import annotations

import logging
import os
from dataclasses import replace

from pymongo.errors import PyMongoError

from app.models.almacen import AlmacenNoDisponible

from app.catalogo_maquinas import TARIFAS_COP_POR_HORA, construir_catalogo
from app.database import motor, transaccion
from app.documentos.store import ejecutar_mongo
from app.factories import crear_candado_repositorio, crear_maquina_documentos_repositorio
from app.security import hash_password

logger = logging.getLogger(__name__)

_MAQUINARIAS = [
    # marca, descripcion, capacidad, modelo, costo_por_hora, placa, categoria
    ("Caterpillar", "Excavadora hidráulica de orugas", "0,12 m³", "320D", 85000, "MSP-001", "Excavadora"),
    ("Komatsu", "Excavadora hidráulica de orugas", "0,15 m³", "PC200", 92000, "MSP-002", "Excavadora"),
    ("JCB", "Retroexcavadora todoterreno", "0,10 m³", "3CX", 70000, "MSP-003", "Retroexcavadora"),
    ("Kenworth", "Volqueta doble troque", "14 m³", "T800", 65000, "MSP-004", "Volqueta"),
]


def _sembrar_maquinas(filas) -> None:
    """Los reinicios conservan las ediciones, incluso las bajas por placa."""
    with transaccion(serializar="catalogo") as db:
        categorias = {
            fila["nombre_categoria"]: fila["id_categoria"]
            for fila in db.execute("SELECT id_categoria, nombre_categoria FROM categorias").fetchall()
        }
        placas = {fila["placa"] for fila in db.execute("SELECT placa FROM maquinarias").fetchall()}
        for marca, descripcion, capacidad, modelo, costo, placa, categoria in filas:
            if placa in placas:
                continue
            if categoria not in categorias:
                fila = db.execute(
                    "INSERT INTO categorias (nombre_categoria) VALUES (?) RETURNING id_categoria",
                    (categoria,),
                ).fetchone()
                categorias[categoria] = fila["id_categoria"]
            db.execute(
                """INSERT INTO maquinarias
                   (marca, descripcion, capacidad, modelo, costo_por_hora, placa, id_categoria)
                   VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT (placa) DO NOTHING""",
                (marca, descripcion, capacidad, modelo, costo, placa, categorias[categoria]),
            )
            placas.add(placa)


def seed_catalogo_real(*, sembrar_sql: bool = True) -> None:
    catalogo = construir_catalogo()
    if sembrar_sql:
        _sembrar_maquinas(
            (doc.marca, doc.descripcion, doc.capacidad, doc.modelo,
             TARIFAS_COP_POR_HORA.get(doc.placa, 0.0), doc.placa, doc.categoria)
            for doc in catalogo
        )
    try:
        _sembrar_mongo(catalogo)
    except (PyMongoError, AlmacenNoDisponible) as error:
        logger.error(
            "No se pudo cargar el catálogo en MongoDB (revisa MONGODB_URI): %s", type(error).__name__
        )


def _sembrar_mongo(catalogo) -> None:

    candado = crear_candado_repositorio()  # Factory Method
    if not ejecutar_mongo(lambda: candado.adquirir("seed_catalogo")):

        logger.info("Otro proceso está cargando el catálogo en MongoDB; se omite aquí.")
        return
    try:
        documentos = crear_maquina_documentos_repositorio()  # Factory Method
        documentos.asegurar_indices()
        for doc in catalogo:
            documentos.insertar_si_falta(replace(doc, imagenes=[]))
    finally:
        ejecutar_mongo(lambda: candado.liberar("seed_catalogo"))


def seed_demo_data() -> None:

    with transaccion() as db:
        catalogo_existente = bool(db.execute("SELECT 1 FROM maquinarias LIMIT 1").fetchone())
    sembrar_sql = motor() != "postgresql" or not catalogo_existente
    if sembrar_sql:
        _sembrar_maquinas(_MAQUINARIAS)
    with transaccion(serializar="admin_inicial") as db:
        if not db.execute("SELECT 1 FROM administradores LIMIT 1").fetchone():
            clave = os.getenv("MSPS_ADMIN_PASSWORD")
            if motor() == "postgresql" and not clave:
                raise RuntimeError("Define MSPS_ADMIN_PASSWORD para crear el primer admin de la web.")
            fila = db.execute(
                """INSERT INTO usuarios (nombre, contrasena_hash, id_rol)
                   SELECT ?, ?, id_rol FROM roles WHERE nombre = 'administrador'
                   RETURNING id_usuario""",
                ("admin", hash_password(clave or "admin123")),
            ).fetchone()
            db.execute("INSERT INTO administradores (id_usuario) VALUES (?)", (fila["id_usuario"],))
    seed_catalogo_real(sembrar_sql=sembrar_sql)