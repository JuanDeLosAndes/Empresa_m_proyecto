import hashlib
import json
import re
import secrets
import time

from collections.abc import Callable
from app.database import ERRORES_INTEGRIDAD, transaccion
from app.models.credenciales import CampoInvalido, validar_cedula, validar_contrasena, validar_correo, validar_telefono
from app.security import hash_password


def validar_nit(valor: str) -> str:
    # Formato empresarial elegido para este formulario: 9 dígitos y DV opcional.
    valor = valor.strip()
    if not re.fullmatch(r"(?:[0-9]{9}|[0-9]{3}\.[0-9]{3}\.[0-9]{3})(?:-[0-9])?|[0-9]{10}", valor):
        raise CampoInvalido("nit", "El NIT debe tener 9 números, con un dígito de verificación opcional. Ejemplo: 900123456-7.")
    digitos = valor.replace(".", "").replace("-", "")
    return digitos[:9]  # La identidad no depende de cómo se escribió el DV.


def comprobar_duplicados(db, tipo, datos):
    correo = datos["correo"]
    existe = db.execute(
        """SELECT 1 FROM personas_naturales WHERE lower(correo) = ?
           UNION ALL SELECT 1 FROM empresas WHERE lower(correo) = ?""",
        (correo, correo),
    ).fetchone()
    if existe:
        raise CampoInvalido("correo", "Ese correo ya está registrado. Inicia sesión.")
    if tipo == "persona":
        if db.execute("SELECT 1 FROM usuarios WHERE nombre = ?", (datos["nombre"],)).fetchone():
            raise CampoInvalido("usuario", "Ese usuario ya está registrado.")
        if db.execute("SELECT 1 FROM personas_naturales WHERE cedula = ?", (datos["cedula"],)).fetchone():
            raise CampoInvalido("cedula", "Esa cédula ya está registrada.")
    else:
        filas = db.execute("SELECT nit FROM empresas").fetchall()
        if any(f["nit"].replace(".", "").replace("-", "")[:9] == datos["nit"] for f in filas):
            raise CampoInvalido("nit", "Ese NIT ya está registrado.")


def solicitar(tipo: str, nombre: str, correo: str, contrasena: str, documento: str,
              *, enviar: Callable[[str, str], None], telefono: str = "", direccion: str = "") -> None:
    correo = validar_correo(correo)
    validar_contrasena(contrasena)
    nombre = nombre.strip()
    if not nombre or len(nombre) > 120:
        raise CampoInvalido("usuario" if tipo == "persona" else "nombre_empresa", "Escribe un nombre de hasta 120 caracteres.")
    datos = {"nombre": nombre, "correo": correo}
    if tipo == "empresa":
        if len(direccion.strip()) > 250:
            raise CampoInvalido("direccion", "La dirección admite hasta 250 caracteres.")
        datos["direccion"] = direccion.strip() or None
        datos["nit"] = validar_nit(documento)
    elif tipo == "persona":
        documento = validar_cedula(documento)
        datos["telefono"] = validar_telefono(telefono)
        datos["cedula"] = documento
    else:
        raise ValueError("Tipo de cuenta inválido.")
    ahora = int(time.time())
    token = secrets.token_urlsafe(32)
    huella = hashlib.sha256(token.encode()).hexdigest()
    datos["contrasena_hash"] = hash_password(contrasena)
    with transaccion(serializar="registro") as db:
        db.execute("DELETE FROM registros_pendientes WHERE vence < ?", (ahora,))
        comprobar_duplicados(db, tipo, datos)
        anterior = db.execute("SELECT creado FROM registros_pendientes WHERE correo = ?", (correo,)).fetchone()
        if anterior and ahora - anterior["creado"] < 60:
            raise ValueError("Espera un minuto antes de volver a solicitar el correo.")
        db.execute("DELETE FROM registros_pendientes WHERE correo = ?", (correo,))
        db.execute("INSERT INTO registros_pendientes VALUES (?, ?, ?, ?, ?, ?)",
                   (huella, correo, tipo, json.dumps(datos), ahora, ahora + 1800))
    try:
        enviar(correo, token)
    except Exception:
        with transaccion() as db:
            db.execute("DELETE FROM registros_pendientes WHERE token_hash = ?", (huella,))
        raise


def confirmar(token: str) -> None:
    if not token or len(token) > 200:
        raise ValueError("Enlace inválido.")
    huella = hashlib.sha256(token.encode()).hexdigest()
    try:
        with transaccion(serializar="registro") as db:
            fila = db.execute("SELECT * FROM registros_pendientes WHERE token_hash = ?", (huella,)).fetchone()
            if not fila or fila["vence"] < int(time.time()):
                raise ValueError("El enlace venció o ya fue usado. Puedes volver a registrarte para recibir otro.")
            datos = json.loads(fila["datos"])
            comprobar_duplicados(db, fila["tipo"], datos)
            if fila["tipo"] == "empresa":
                db.execute(
                    """INSERT INTO empresas(nombre, nit, correo, direccion, contrasena_hash, id_rol)
                       VALUES (?, ?, ?, ?, ?, (SELECT id_rol FROM roles WHERE nombre='empresa'))""",
                    (datos["nombre"], datos["nit"], datos["correo"], datos.get("direccion"), datos["contrasena_hash"]),
                )
            else:
                cursor = db.execute(
                    """INSERT INTO usuarios(nombre, contrasena_hash, id_rol)
                       VALUES (?, ?, (SELECT id_rol FROM roles WHERE nombre='persona_natural')) RETURNING id_usuario""",
                    (datos["nombre"], datos["contrasena_hash"]),
                )
                db.execute(
                    "INSERT INTO personas_naturales(id_usuario, cedula, correo, telefono) VALUES (?, ?, ?, ?)",
                    (cursor.fetchone()["id_usuario"], datos["cedula"], datos["correo"], datos.get("telefono")),
                )
            db.execute("DELETE FROM registros_pendientes WHERE token_hash = ?", (huella,))
    except ERRORES_INTEGRIDAD as error:
        raise ValueError("Los datos ya pertenecen a una cuenta registrada.") from error