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

from app.database import get_connection
from app.models.categoria import CategoriaModel
from app.models.maquinaria import MaquinariaModel
from app.models.usuario import UsuarioModel, ROL_ADMINISTRADOR

_CATEGORIAS = ["Excavadora", "Retroexcavadora", "Volqueta"]

_MAQUINARIAS = [
    # marca, descripcion, capacidad, modelo, costo_por_hora, placa, categoria
    ("Caterpillar", "Excavadora hidráulica de orugas", "0,12 m³", "320D", 85000, "MSP-001", "Excavadora"),
    ("Komatsu", "Excavadora hidráulica de orugas", "0,15 m³", "PC200", 92000, "MSP-002", "Excavadora"),
    ("JCB", "Retroexcavadora todoterreno", "0,10 m³", "3CX", 70000, "MSP-003", "Retroexcavadora"),
    ("Kenworth", "Volqueta doble troque", "14 m³", "T800", 65000, "MSP-004", "Volqueta"),
]


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
    hay_admin = conn.execute(
        "SELECT 1 FROM usuarios WHERE rol = ?", (ROL_ADMINISTRADOR,)
    ).fetchone()
    if not hay_admin:
        UsuarioModel.crear_administrador(nombre="admin", contrasena="admin123")