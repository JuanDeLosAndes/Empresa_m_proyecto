from __future__ import annotations

import logging
import os
import sqlite3
from dataclasses import replace

from pymongo.errors import PyMongoError

from app.catalogo_maquinas import TARIFAS_COP_POR_HORA, construir_catalogo
from app.database import get_connection
from app.documentos.store import ejecutar_mongo
from app.factories import crear_candado_repositorio, crear_maquina_documentos_repositorio
from app.models.categoria import CategoriaModel
from app.models.maquinaria import MaquinariaModel
from app.models.usuario import UsuarioModel

logger = logging.getLogger(__name__)

_CATEGORIAS = ["Excavadora", "Retroexcavadora", "Volqueta"]

_MAQUINARIAS = [
    # marca, descripcion, capacidad, modelo, costo_por_hora, placa, categoria
    ("Caterpillar", "Excavadora hidráulica de orugas", "0,12 m³", "320D", 85000, "MSP-001", "Excavadora"),
    ("Komatsu", "Excavadora hidráulica de orugas", "0,15 m³", "PC200", 92000, "MSP-002", "Excavadora"),
    ("JCB", "Retroexcavadora todoterreno", "0,10 m³", "3CX", 70000, "MSP-003", "Retroexcavadora"),
    ("Kenworth", "Volqueta doble troque", "14 m³", "T800", 65000, "MSP-004", "Volqueta"),
]


def _obtener_o_crear_categoria(nombre: str):
    categoria = CategoriaModel.obtener_por_nombre(nombre)
    if categoria is not None:
        return categoria
    try:
        return CategoriaModel.crear(nombre)
    except sqlite3.IntegrityError:
        # Otro worker la creó justo antes; se lee la que ya existe.
        return CategoriaModel.obtener_por_nombre(nombre)


def seed_catalogo_real() -> None:
    """Carga la flota real en dos motores, enlazados por la placa:
    - SQL (SQLite): la fila de la máquina (lo transaccional: carrito, alquileres).
    - MongoDB: el documento con la ficha técnica. Las FOTOS no se siembran: las
      sube el administrador desde /admin/maquinas.

    Idempotente: no duplica filas SQL ni pisa documentos de MongoDB que ya existen.
    Si MongoDB no responde, el sitio sigue funcionando (sin galería ni ficha)
    y se deja el aviso en el log.
    """
    conn = get_connection()
    catalogo = construir_catalogo()  # Director + Builder + Factory de fichas

    for doc in catalogo:
        categoria = _obtener_o_crear_categoria(doc.categoria)
        existe = conn.execute(
            "SELECT 1 FROM maquinarias WHERE placa = ?", (doc.placa,)
        ).fetchone()
        if not existe:
            try:
                MaquinariaModel.crear(
                    marca=doc.marca,
                    descripcion=doc.descripcion,
                    capacidad=doc.capacidad,
                    modelo=doc.modelo,
                    # Sin tarifa definida = 0, y el sitio muestra "Tarifa por cotizar".
                    costo_por_hora=TARIFAS_COP_POR_HORA.get(doc.placa, 0.0),
                    placa=doc.placa,
                    id_categoria=categoria.id_categoria,
                )
            except sqlite3.IntegrityError:
                # Otro worker de gunicorn la insertó justo antes (placa UNIQUE).
                pass

    try:
        _sembrar_mongo(catalogo)
    except PyMongoError as error:
        logger.error(
            "No se pudo cargar el catálogo en MongoDB (revisa MONGODB_URI): %s", type(error).__name__
        )


def _sembrar_mongo(catalogo) -> None:
    """Crea en MongoDB la ficha técnica de cada máquina que todavía no la tenga.

    Las FOTOS no se siembran: las gestiona el administrador desde /admin/maquinas y
    viven únicamente en MongoDB (GridFS). Por eso el seed nunca pisa un documento
    que ya existe: así no borra las fotos ni las ediciones que haya hecho el admin.
    """
    candado = crear_candado_repositorio()  # Factory Method
    if not ejecutar_mongo(lambda: candado.adquirir("seed_catalogo")):
        # Otro proceso (p. ej. el padre/hijo de uvicorn --reload) ya está cargando el
        # catálogo: no se compite con él.
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
    conn = get_connection()

    for nombre in _CATEGORIAS:
        if not CategoriaModel.obtener_por_nombre(nombre):
            CategoriaModel.crear(nombre)

    for marca, descripcion, capacidad, modelo, costo, placa, nombre_categoria in _MAQUINARIAS:
        existe = conn.execute(
            "SELECT 1 FROM maquinarias WHERE placa = ?", (placa,)
        ).fetchone()
        if existe:
            continue
        categoria = CategoriaModel.obtener_por_nombre(nombre_categoria)
        if not categoria:
            continue
        MaquinariaModel.crear(
            marca=marca,
            descripcion=descripcion,
            capacidad=capacidad,
            modelo=modelo,
            costo_por_hora=costo,
            placa=placa,
            id_categoria=categoria.id_categoria,
        )

    # Administrador por defecto para poder probar el login con rol
    # administrador. Se crea solo si no existe ningún administrador
    # todavía; por seguridad esto NO se expone en ningún formulario
    # público de registro (ver app/models/usuario.py).
    hay_admin = conn.execute("SELECT 1 FROM administradores").fetchone()
    if not hay_admin:
        UsuarioModel.crear_administrador(
            nombre="admin",
            # En producción define MSPS_ADMIN_PASSWORD; el valor por defecto es solo para desarrollo.
            contrasena=os.environ.get("MSPS_ADMIN_PASSWORD", "admin123"),
        )

    seed_catalogo_real()