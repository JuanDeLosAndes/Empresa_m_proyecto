from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.database import get_connection


@dataclass
class Pago:
    id_pago: int
    referencia: str
    cliente_tipo: str
    cliente_id: int
    monto: int
    proveedor: str
    estado: str
    transaccion_id: Optional[str]
    detalle: str
    fecha: str

    @staticmethod
    def _from_row(row) -> "Pago":
        return Pago(**{campo: row[campo] for campo in Pago.__dataclass_fields__})


class PagoModel:
    @staticmethod
    def crear(referencia: str, cliente_tipo: str, cliente_id: int,
              monto: int, proveedor: str, detalle: str) -> Pago:
        conn = get_connection()
        conn.execute(
            """INSERT INTO pagos (referencia, cliente_tipo, cliente_id, monto, proveedor, detalle)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (referencia, cliente_tipo, cliente_id, monto, proveedor, detalle),
        )
        conn.commit()
        return PagoModel.obtener_por_referencia(referencia)

    @staticmethod
    def obtener_por_referencia(referencia: str) -> Optional[Pago]:
        fila = get_connection().execute(
            "SELECT * FROM pagos WHERE referencia = ?", (referencia,)
        ).fetchone()
        return Pago._from_row(fila) if fila else None

    @staticmethod
    def actualizar_estado(referencia: str, estado: str, transaccion_id: Optional[str] = None) -> None:
        conn = get_connection()
        conn.execute(
            "UPDATE pagos SET estado = ?, transaccion_id = COALESCE(?, transaccion_id) WHERE referencia = ?",
            (estado, transaccion_id, referencia),
        )
        conn.commit()
