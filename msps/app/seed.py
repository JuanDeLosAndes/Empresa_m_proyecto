# ======================================================================
# QUÉ HACE
#   Carga los datos iniciales cada vez que arranca la app: categorías y 4 máquinas de
#   ejemplo, un administrador por defecto, y el catálogo real (filas en SQL +
#   documentos y fotos en MongoDB).
# HASTA DÓNDE LLEGA (y qué NO hace)
#   Solo siembra. Es idempotente: si ya existe, no duplica. Si MongoDB no responde,
#   deja el error en el log y el sitio sigue funcionando. No define los datos reales
#   (catalogo_maquinas.py).
# ======================================================================
"""
Datos de ejemplo de MSPS.

Reemplaza las máquinas y categorías que antes estaban escritas a mano
directamente en las plantillas (buscar_maquinas.html, detalle_maquina.html),
lo cual violaba MVC: una Vista no debería contener datos de negocio,
esos datos deben venir del Modelo. `seed_demo_data()` es idempotente
(usa INSERT OR IGNORE) así que se puede llamar en cada arranque sin
duplicar filas.
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from pymongo.errors import PyMongoError

from app.catalogo_maquinas import TARIFAS_COP_POR_HORA, construir_catalogo
from app.database import get_connection
from app.factories import (
    crear_candado_repositorio,
    crear_imagenes_repositorio,
    crear_maquina_documentos_repositorio,
)
from app.models.categoria import CategoriaModel
from app.models.maquinaria import MaquinariaModel
from app.models.usuario import UsuarioModel

logger = logging.getLogger(__name__)

# Fotos procesadas que se suben a MongoDB (GridFS) en el seed. NO se sirven
# como archivos estáticos: el sitio las lee desde la base (ruta /media/maquinas/...).
RUTA_IMAGENES_SEMILLA = Path(__file__).resolve().parent / "seed_data" / "imagenes_maquinas"

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
    - MongoDB: el documento con la ficha técnica y las FOTOS (GridFS).

    Idempotente: no duplica filas SQL ni reescribe documentos o fotos sin cambios.
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
            "No se pudo cargar el catálogo en MongoDB (revisa MONGODB_URI): %s", error
        )


def _sembrar_mongo(catalogo) -> None:
    candado = crear_candado_repositorio()  # Factory Method
    if not candado.adquirir("seed_catalogo"):
        # Otro proceso (p. ej. el padre/hijo de uvicorn --reload) ya está cargando el
        # catálogo: no se compite con él, porque dos subidas simultáneas dañan fotos.
        logger.info("Otro proceso está cargando el catálogo en MongoDB; se omite aquí.")
        return
    try:
        documentos = crear_maquina_documentos_repositorio()  # Factory Method
        imagenes = crear_imagenes_repositorio()  # Factory Method
        documentos.asegurar_indices()

        for doc in catalogo:
            for imagen in doc.imagenes:
                ruta = RUTA_IMAGENES_SEMILLA / imagen.archivo
                imagenes.guardar(imagen.archivo, ruta.read_bytes())
            # El documento se guarda al final: si una foto falla, no queda una
            # ficha apuntando a imágenes que no existen.
            documentos.guardar(doc)
    finally:
        candado.liberar("seed_catalogo")


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
        UsuarioModel.crear_administrador(nombre="admin", contrasena="admin123")

    seed_catalogo_real()

# ======================================================================
# CÓMO LO HACE (en concreto)
#   - seed_demo_data(): crea categorías y las 4 máquinas de ejemplo si faltan, crea
#     el usuario admin si no hay ningún administrador, y al final llama
#     seed_catalogo_real().
#   - seed_catalogo_real(): construye el catálogo; por cada máquina crea su categoría
#     si falta e inserta la fila SQL si la placa no existe (tarifa =
#     TARIFAS_COP_POR_HORA.get(placa, 0)).
#   - _sembrar_mongo(): toma el candado; sube cada foto desde
#     app/seed_data/imagenes_maquinas con imagenes.guardar(...); guarda el documento
#     con documentos.guardar(...); suelta el candado en el finally. El documento se
#     guarda DESPUÉS de sus fotos.
# USA
#   catalogo_maquinas.py, models/categoria.py, models/maquinaria.py,
#   models/usuario.py, factories.py (candado, imágenes, documentos).
# DÓNDE SE LLAMA
#   app/__init__.py: seed_demo_data() dentro de create_app().
# ======================================================================
