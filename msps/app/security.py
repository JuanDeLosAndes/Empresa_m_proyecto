"""
Utilidades de seguridad de MSPS: hashing de contraseñas y firma de la
cookie de sesión.

Vive fuera de los Modelos y Controladores porque es una utilidad
transversal (no es dato de negocio ni orquestación de rutas):
- Los Modelos (app/models/usuario.py, app/models/empresa.py) la usan
  para no guardar contraseñas en texto plano.
- Los Controladores (app/controllers/auth_controller.py) la usan para
  emitir y leer la cookie de sesión.

La firma de sesión es stateless (no depende de guardar nada en
memoria del servidor), a propósito: el proyecto se despliega con
`gunicorn -w 4` (ver startup.sh), es decir con varios procesos, y una
sesión guardada solo en memoria de un worker no la verían los demás.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets

# En producción, definir MSPS_SECRET_KEY como variable de entorno real
# (por ejemplo en el .env que ya carga python-dotenv). Este valor por
# defecto solo sirve para desarrollo local.
SECRET_KEY = os.environ.get("MSPS_SECRET_KEY", "clave-de-desarrollo-cambiar-en-produccion")

SESSION_COOKIE_NAME = "msps_session"

_ITERACIONES_PBKDF2 = 260_000


def hash_password(password: str) -> str:
    """Genera 'salt$hash' usando PBKDF2-HMAC-SHA256. Nunca se guarda
    la contraseña original."""
    salt = secrets.token_hex(16)
    derivado = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), _ITERACIONES_PBKDF2
    )
    return f"{salt}${derivado.hex()}"


def verify_password(password: str, hash_almacenado: str) -> bool:
    """Verifica una contraseña contra el hash guardado en la base de datos."""
    try:
        salt, derivado_hex = hash_almacenado.split("$", 1)
    except ValueError:
        return False
    derivado = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), _ITERACIONES_PBKDF2
    )
    return hmac.compare_digest(derivado.hex(), derivado_hex)


def firmar_sesion(tipo: str, id_: int) -> str:
    """Arma el valor de la cookie de sesión: 'tipo:id:firma'."""
    payload = f"{tipo}:{id_}"
    firma = hmac.new(SECRET_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}:{firma}"


def leer_sesion(cookie_valor: str | None) -> tuple[str, int] | None:
    """Valida la cookie de sesión y devuelve (tipo, id) o None si no es válida."""
    if not cookie_valor:
        return None
    partes = cookie_valor.split(":")
    if len(partes) != 3:
        return None
    tipo, id_str, firma = partes
    payload = f"{tipo}:{id_str}"
    firma_esperada = hmac.new(SECRET_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(firma, firma_esperada):
        return None
    if not id_str.isdigit():
        return None
    return tipo, int(id_str)