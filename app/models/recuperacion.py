from collections.abc import Callable
import hashlib
import secrets
import time

from app.database import transaccion
from app.models.credenciales import validar_contrasena, validar_correo
from app.security import hash_password


def _huella(token):
    return hashlib.sha256(token.encode()).hexdigest()


def _titular(db, correo):
    return db.execute(
        """SELECT 'persona' AS tipo, id_usuario AS id FROM personas_naturales WHERE lower(correo) = ?
           UNION ALL SELECT 'empresa', id_empresa FROM empresas WHERE lower(correo) = ?""",
        (correo, correo),
    ).fetchall()


def solicitar(correo: str, enviar: Callable[[str, str], None]) -> None:
    correo = validar_correo(correo)
    ahora = int(time.time())
    token = secrets.token_urlsafe(32)
    huella = _huella(token)
    with transaccion(serializar="recuperacion") as db:
        db.execute("DELETE FROM recuperaciones WHERE vence <= ?", (ahora,))
        titulares = _titular(db, correo)
        if len(titulares) != 1:
            return
        previo = db.execute("SELECT creado FROM recuperaciones WHERE correo = ?", (correo,)).fetchone()
        if previo and ahora - previo["creado"] < 60:
            return
        db.execute("DELETE FROM recuperaciones WHERE correo = ?", (correo,))
        db.execute("INSERT INTO recuperaciones(token_hash, correo, tipo, titular, creado, vence) VALUES (?,?,?,?,?,?)",
                   (huella, correo, titulares[0]["tipo"], titulares[0]["id"], ahora, ahora + 1800))
    try:
        enviar(correo, token)
    except Exception:
        with transaccion() as db:
            db.execute("DELETE FROM recuperaciones WHERE token_hash = ?", (huella,))
        raise


def confirmar(token, contrasena):
    validar_contrasena(contrasena)
    if not token or len(token) > 128:
        raise ValueError("Enlace inválido.")
    with transaccion(serializar="recuperacion") as db:
        fila = db.execute("SELECT * FROM recuperaciones WHERE token_hash = ?", (_huella(token),)).fetchone()
        if not fila or fila["vence"] <= int(time.time()):
            raise ValueError("El enlace venció o ya fue utilizado. Solicita uno nuevo.")
        titulares = _titular(db, fila["correo"])
        if len(titulares) != 1 or (titulares[0]["id"], titulares[0]["tipo"]) != (fila["titular"], fila["tipo"]):
            raise ValueError("La cuenta cambió. Solicita otro enlace.")
        consulta = ("UPDATE usuarios SET contrasena_hash = ? WHERE id_usuario = ?" if fila["tipo"] == "persona"
                    else "UPDATE empresas SET contrasena_hash = ? WHERE id_empresa = ?")
        db.execute(consulta, (hash_password(contrasena), fila["titular"]))
        db.execute("DELETE FROM recuperaciones WHERE token_hash = ?", (fila["token_hash"],))