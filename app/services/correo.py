import os
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import urlparse


class CorreoNoDisponible(RuntimeError):
    pass


def enviar_verificacion(destino: str, token: str) -> None:
    _enviar(destino, "Confirma tu correo", "verificar-correo", token,
            "Abre este enlace y confirma tu dirección para activar tu cuenta.")


def enviar_recuperacion(destino: str, token: str) -> None:
    _enviar(destino, "Restablece tu contraseña", "restablecer", token,
            "Abre este enlace para elegir una nueva contraseña.")


def _enviar(destino, asunto, ruta, token, instruccion):
    host = os.getenv("SMTP_HOST", "")
    usuario = os.getenv("SMTP_USER", "")
    clave = os.getenv("SMTP_PASSWORD", "")
    remitente = os.getenv("SMTP_FROM", usuario)
    base = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
    url = urlparse(base)
    if not host or not usuario or not clave or not remitente or url.scheme not in ("http", "https") or not url.hostname or url.path or url.query or url.fragment:
        raise CorreoNoDisponible("Falta configurar el correo del servidor.")
    mensaje = EmailMessage()
    mensaje["From"] = remitente
    mensaje["To"] = destino
    mensaje["Subject"] = asunto + " · MSPS"
    mensaje.set_content(f"{instruccion}\n\n{base}/{ruta}?token={token}\n\n"
                        "El enlace vence en 30 minutos. Si no lo solicitaste, ignora este correo.")
    try:
        puerto = int(os.getenv("SMTP_PORT", "587"))
        contexto = ssl.create_default_context()
        if puerto == 465:
            servidor = smtplib.SMTP_SSL(host, puerto, timeout=20, context=contexto)
        else:
            servidor = smtplib.SMTP(host, puerto, timeout=20)
        with servidor:
            if puerto != 465:
                servidor.starttls(context=contexto)
            servidor.login(usuario, clave)
            servidor.send_message(mensaje)
    except (OSError, smtplib.SMTPException, ValueError) as error:
        raise CorreoNoDisponible("No se pudo enviar el correo. Intenta de nuevo más tarde.") from error