from app.database import transaccion


class SolicitudEnConflicto(ValueError):
    pass


class RegistroNoEncontrado(LookupError):
    pass


def panel_persona(usuario):
    with transaccion() as db:
        actual = db.execute(
            """SELECT e.nombre AS empresa, p.nombre AS pendiente
               FROM usuarios u LEFT JOIN empresas e ON e.id_empresa = u.id_empresa
               LEFT JOIN solicitudes_empresa s ON s.id_usuario = u.id_usuario
               LEFT JOIN empresas p ON p.id_empresa = s.id_empresa WHERE u.id_usuario = ?""",
            (usuario,),
        ).fetchone()
        empresas = db.execute("SELECT id_empresa, nombre, nit FROM empresas ORDER BY nombre").fetchall()
    return {"actual": actual, "empresas": empresas}


def panel_empresa(empresa):
    with transaccion() as db:
        pendientes = db.execute(
            """SELECT u.id_usuario, u.nombre FROM solicitudes_empresa s
               JOIN usuarios u USING(id_usuario) WHERE s.id_empresa = ? ORDER BY u.nombre""",
            (empresa,),
        ).fetchall()
        integrantes = db.execute(
            """SELECT u.id_usuario, u.nombre FROM usuarios u JOIN personas_naturales USING(id_usuario)
               WHERE u.id_empresa = ? ORDER BY u.nombre""", (empresa,),
        ).fetchall()
    return {"pendientes": pendientes, "integrantes": integrantes}


def solicitar(usuario, empresa):
    with transaccion(serializar="afiliacion") as db:
        if not db.execute("SELECT 1 FROM empresas WHERE id_empresa = ?", (empresa,)).fetchone():
            raise RegistroNoEncontrado("Empresa no encontrada")
        actual = db.execute("SELECT id_empresa FROM usuarios WHERE id_usuario = ?", (usuario,)).fetchone()
        if actual is None:
            raise RegistroNoEncontrado("Usuario no encontrado")
        if actual["id_empresa"] is not None:
            raise SolicitudEnConflicto("Ya perteneces a una empresa")
        if db.execute("SELECT 1 FROM solicitudes_empresa WHERE id_usuario = ?", (usuario,)).fetchone():
            raise SolicitudEnConflicto("Ya tienes una solicitud pendiente")
        db.execute("INSERT INTO solicitudes_empresa VALUES (?, ?)", (usuario, empresa))


def resolver(empresa, usuario, aceptar):
    with transaccion(serializar="afiliacion") as db:
        borrada = db.execute("DELETE FROM solicitudes_empresa WHERE id_empresa = ? AND id_usuario = ?",
                             (empresa, usuario))
        if not borrada.rowcount:
            raise RegistroNoEncontrado("Solicitud no encontrada")
        if aceptar:
            alta = db.execute("UPDATE usuarios SET id_empresa = ? WHERE id_usuario = ? AND id_empresa IS NULL",
                              (empresa, usuario))
            if not alta.rowcount:
                raise SolicitudEnConflicto("El usuario ya pertenece a una empresa")


def retirar(empresa, usuario):
    with transaccion(serializar="afiliacion") as db:
        cambio = db.execute(
            """UPDATE usuarios SET id_empresa = NULL WHERE id_empresa = ? AND id_usuario = ?
               AND id_usuario IN (SELECT id_usuario FROM personas_naturales)""", (empresa, usuario),
        )
        if not cambio.rowcount:
            raise RegistroNoEncontrado("Integrante no encontrado en tu empresa")
