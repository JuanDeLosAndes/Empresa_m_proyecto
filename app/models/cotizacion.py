from app.database import transaccion


def registrar(id_maquinaria, nombre, email, telefono, mensaje):
    with transaccion() as db:
        fila = db.execute(
            """INSERT INTO cotizaciones (id_maquinaria, nombre, email, telefono, mensaje)
               SELECT id_maquinaria, ?, ?, ?, ? FROM maquinarias WHERE id_maquinaria = ? AND eliminada = 0
               RETURNING id_cotizacion""",
            (nombre, email, telefono, mensaje, id_maquinaria),
        ).fetchone()
        if fila is None:
            raise LookupError("Máquina no encontrada")
        return fila["id_cotizacion"]
