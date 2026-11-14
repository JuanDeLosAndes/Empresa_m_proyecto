from app.database import transaccion


def registrar(id_maquinaria, nombre, email, telefono, mensaje):
    with transaccion() as db:
        fila = db.execute(
            """INSERT INTO cotizaciones (id_maquinaria, nombre, email, telefono, mensaje)
               SELECT id_maquinaria, ?, ?, ?, ? FROM maquinarias WHERE id_maquinaria = ?""",
            (nombre, email, telefono, mensaje, id_maquinaria),
        )
        if not fila.rowcount:
            raise LookupError("Máquina no encontrada")
        return fila.lastrowid