"""
Modelo de Factura para Empresa (la M de MVC).

Encapsula el acceso a la tabla `facturas_empresa`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.database import get_connection


@dataclass
class FacturaEmpresa:
    id_factura_empresa: int
    nit: str
    correo: str
    metodo_pago: str
    costo: float
    fecha: str
    id_alquiler: int
    id_empresa: int

    @staticmethod
    def _from_row(row) -> "FacturaEmpresa":
        return FacturaEmpresa(
            id_factura_empresa=row["id_factura_empresa"],
            nit=row["nit"],
            correo=row["correo"],
            metodo_pago=row["metodo_pago"],
            costo=row["costo"],
            fecha=row["fecha"],
            id_alquiler=row["id_alquiler"],
            id_empresa=row["id_empresa"],
        )


class FacturaEmpresaModel:
    @staticmethod
    def crear(
        nit: str,
        correo: str,
        metodo_pago: str,
        costo: float,
        id_alquiler: int,
        id_empresa: int,
    ) -> FacturaEmpresa:
        conn = get_connection()
        cursor = conn.execute(
            """INSERT INTO facturas_empresa
                   (nit, correo, metodo_pago, costo, id_alquiler, id_empresa)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (nit, correo, metodo_pago, costo, id_alquiler, id_empresa),
        )
        conn.commit()
        factura = FacturaEmpresaModel.obtener_por_id(cursor.lastrowid)
        assert factura is not None
        return factura

    @staticmethod
    def obtener_por_id(id_factura_empresa: int) -> Optional[FacturaEmpresa]:
        conn = get_connection()
        fila = conn.execute(
            "SELECT * FROM facturas_empresa WHERE id_factura_empresa = ?",
            (id_factura_empresa,),
        ).fetchone()
        return FacturaEmpresa._from_row(fila) if fila else None

    @staticmethod
    def listar_por_empresa(id_empresa: int) -> list[FacturaEmpresa]:
        conn = get_connection()
        filas = conn.execute(
            "SELECT * FROM facturas_empresa WHERE id_empresa = ? ORDER BY fecha DESC",
            (id_empresa,),
        ).fetchall()
        return [FacturaEmpresa._from_row(f) for f in filas]