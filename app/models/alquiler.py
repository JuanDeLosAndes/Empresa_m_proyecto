from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.database import transaccion

ESTADO_OCUPADA = "ocupada"
ESTADO_DESOCUPADA = "desocupada"

APROBACION_PENDIENTE = "pendiente"
APROBACION_APROBADO = "aprobado"
APROBACION_RECHAZADO = "rechazado"


@dataclass
class Alquiler:
    id_alquiler: int
    fecha_inicio: str
    fecha_fin: Optional[str]
    estado_ocupacion: str
    estado_aprobacion: str
    id_usuario: int
    id_maquinaria: int

    @staticmethod
    def _from_row(row) -> "Alquiler":
        return Alquiler(
            id_alquiler=row["id_alquiler"],
            fecha_inicio=row["fecha_inicio"],
            fecha_fin=row["fecha_fin"],
            estado_ocupacion=row["estado_ocupacion"],
            estado_aprobacion=row["estado_aprobacion"],
            id_usuario=row["id_usuario"],
            id_maquinaria=row["id_maquinaria"],
        )


class AlquilerModel:
    @staticmethod
    def crear(
        fecha_inicio: str,
        id_usuario: int,
        id_maquinaria: int,
        fecha_fin: Optional[str] = None,
    ) -> Alquiler:
        with transaccion() as conn:
            cursor = conn.execute(
                """INSERT INTO alquileres
                       (fecha_inicio, fecha_fin, id_usuario, id_maquinaria)
                   VALUES (?, ?, ?, ?) RETURNING *""",
                (fecha_inicio, fecha_fin, id_usuario, id_maquinaria),
            )
            return Alquiler._from_row(cursor.fetchone())

    @staticmethod
    def obtener_por_id(id_alquiler: int) -> Optional[Alquiler]:
        with transaccion() as conn:
            fila = conn.execute(
                "SELECT * FROM alquileres WHERE id_alquiler = ?", (id_alquiler,)
            ).fetchone()
            return Alquiler._from_row(fila) if fila else None

    @staticmethod
    def listar_por_usuario(id_usuario: int) -> list[Alquiler]:
        with transaccion() as conn:
            filas = conn.execute(
                "SELECT * FROM alquileres WHERE id_usuario = ? ORDER BY fecha_inicio DESC",
                (id_usuario,),
            ).fetchall()
            return [Alquiler._from_row(f) for f in filas]

    @staticmethod
    def actualizar_estado_aprobacion(id_alquiler: int, estado_aprobacion: str) -> None:
        with transaccion() as conn:
            conn.execute(
                "UPDATE alquileres SET estado_aprobacion = ? WHERE id_alquiler = ?",
                (estado_aprobacion, id_alquiler),
            )