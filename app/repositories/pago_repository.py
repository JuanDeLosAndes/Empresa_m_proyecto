from __future__ import annotations

from app.database import transaccion


class PagoRepositorioSQLite:
    def crear_o_reutilizar(self, pedido: dict) -> dict:
        with transaccion() as db:
            db.execute("BEGIN IMMEDIATE")
            anterior = db.execute(
                """SELECT * FROM pedidos_pago WHERE propietario_tipo = ? AND propietario_id = ?
                   AND ambiente = ? AND huella = ? AND estado = 'PENDING' AND vence > ?
                   ORDER BY creada DESC LIMIT 1""",
                (pedido["propietario_tipo"], pedido["propietario_id"], pedido["ambiente"], pedido["huella"], pedido["creada"]),
            ).fetchone()
            if anterior:
                return dict(anterior)
            campos = list(pedido)
            db.execute(f"INSERT INTO pedidos_pago ({', '.join(campos)}) VALUES ({', '.join('?' for _ in campos)})",
                       [pedido[c] for c in campos])
            return dict(db.execute("SELECT * FROM pedidos_pago WHERE referencia = ?", (pedido["referencia"],)).fetchone())

    def obtener(self, referencia: str) -> dict | None:
        with transaccion() as db:
            fila = db.execute("SELECT * FROM pedidos_pago WHERE referencia = ?", (referencia,)).fetchone()
            return dict(fila) if fila else None

    def listar(self, tipo: str, identificador: int, administrador=False) -> list[dict]:
        with transaccion() as db:
            if administrador:
                filas = db.execute("SELECT * FROM pedidos_pago ORDER BY creada DESC LIMIT 100").fetchall()
            else:
                filas = db.execute(
                    "SELECT * FROM pedidos_pago WHERE propietario_tipo = ? AND propietario_id = ? ORDER BY creada DESC LIMIT 100",
                    (tipo, identificador),
                ).fetchall()
            return [dict(f) for f in filas]

    def actualizar(self, referencia: str, datos: dict, ahora: int) -> dict:
        with transaccion() as db:
            db.execute("BEGIN IMMEDIATE")
            fila = db.execute("SELECT * FROM pedidos_pago WHERE referencia = ?", (referencia,)).fetchone()
            if not fila:
                raise LookupError("Pedido no encontrado.")
            pedido = dict(fila)
            if pedido["transaccion_id"] and pedido["transaccion_id"] != datos["id"]:
                raise ValueError("La referencia ya está asociada a otra transacción.")
            estado = datos["status"]
            # Un evento atrasado no puede deshacer un pago aprobado o anulado.
            if pedido["estado"] == "VOIDED" or (pedido["estado"] == "APPROVED" and estado != "VOIDED"):
                return pedido
            if pedido["estado"] in {"DECLINED", "ERROR"} and estado == "PENDING":
                return pedido
            db.execute(
                """UPDATE pedidos_pago SET estado = ?, transaccion_id = ?, metodo_pago = ?, actualizada = ?,
                   pagada = CASE WHEN ? = 'APPROVED' THEN COALESCE(pagada, ?) ELSE pagada END
                   WHERE referencia = ?""",
                (estado, datos["id"], datos.get("payment_method_type", ""), ahora, estado, ahora, referencia),
            )
            return dict(db.execute("SELECT * FROM pedidos_pago WHERE referencia = ?", (referencia,)).fetchone())