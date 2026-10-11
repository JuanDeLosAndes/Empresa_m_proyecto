"""
Modelo de Factura para persona natural (la M de MVC).

Encapsula el acceso a la tabla `facturas`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.database import get_connection


@dataclass
class Factura:
    id_factura: int
    numero: str
    cedula: str
    metodo_pago: str
    costo: float
    iva: float
    fecha: str
    id_alquiler: int

    @staticmethod
    def _from_row(row) -> "Factura":
        return Factura(
            id_factura=row["id_factura"],
            numero=row["numero"],
            cedula=row["cedula"],
            metodo_pago=row["metodo_pago"],
            costo=row["costo"],
            iva=row["iva"],
            fecha=row["fecha"],
            id_alquiler=row["id_alquiler"],
        )


class FacturaModel:
    @staticmethod
    def crear(
        numero: str,
        cedula: str,
        metodo_pago: str,
        costo: float,
        iva: float,
        id_alquiler: int,
    ) -> Factura:
        conn = get_connection()
        cursor = conn.execute(
            """INSERT INTO facturas (numero, cedula, metodo_pago, costo, iva, id_alquiler)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (numero, cedula, metodo_pago, costo, iva, id_alquiler),
        )
        conn.commit()
        factura = FacturaModel.obtener_por_id(cursor.lastrowid)
        assert factura is not None
        return factura

    @staticmethod
    def obtener_por_id(id_factura: int) -> Optional[Factura]:
        conn = get_connection()
        fila = conn.execute(
            "SELECT * FROM facturas WHERE id_factura = ?", (id_factura,)
        ).fetchone()
        return Factura._from_row(fila) if fila else None

    @staticmethod
    def listar_por_cedula(cedula: str) -> list[Factura]:
        conn = get_connection()
        filas = conn.execute(
            "SELECT * FROM facturas WHERE cedula = ? ORDER BY fecha DESC", (cedula,)
        ).fetchall()
        return [Factura._from_row(f) for f in filas]