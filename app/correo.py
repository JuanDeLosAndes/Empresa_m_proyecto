import os
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import urlparse


class CorreoNoDisponible(RuntimeError):
    pass


def enviar_verificacion(destino: str, token: str) -> None:
    host = os.getenv("SMTP_HOST", "")
    usuario = os.getenv("SMTP_USER", "")
    clave = os.getenv("SMTP_PASSWORD", "")
    remitente = os.getenv("SMTP_FROM", usuario)
    base = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
    url = urlparse(base)
    if not host or not usuario or not clave or not remitente or url.scheme not in ("http", "https") or not url.netloc:
        raise CorreoNoDisponible("Falta configurar el correo del servidor.")
    mensaje = EmailMessage()
    mensaje["From"] = remitente
    mensaje["To"] = destino
    mensaje["Subject"] = "Confirma tu correo · MSPS"
    mensaje.set_content(
        "Recibimos una solicitud de registro en MSPS.\n\n"
        f"Para activar tu cuenta, abre {base}/verificar-correo?token={token}\n\n"
        "El enlace vence en 30 minutos. Confirma con el botón de la página.\n"
        "Si no solicitaste esta cuenta, puedes ignorar este mensaje."
    )
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
        raise CorreoNoDisponible("No se pudo enviar el correo. Intenta registrarte nuevamente.") from error