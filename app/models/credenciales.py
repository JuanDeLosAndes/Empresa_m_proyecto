import re

from email_validator import EmailNotValidError, validate_email


class CampoInvalido(ValueError):
    def __init__(self, campo: str, mensaje: str):
        super().__init__(mensaje)
        self.campo = campo


def validar_cedula(valor: str) -> str:
    if not re.fullmatch(r"[1-9][0-9]{0,9}", valor):
        raise CampoInvalido("cedula", "Escribe tu cédula con hasta 10 dígitos, sin puntos ni espacios.")
    return valor


def validar_telefono(valor: str | None) -> str | None:
    if valor is None or valor == "":
        return None
    if not re.fullmatch(r"[0-9]{1,40}", valor):
        raise CampoInvalido("telefono", "Escribe solo números, sin espacios ni símbolos (máximo 40).")
    return valor


def validar_correo(valor: str) -> str:
    try:
        correo = validate_email(valor.strip(), check_deliverability=False)
    except EmailNotValidError as error:
        raise CampoInvalido("correo", "Esto no parece un correo electrónico. Ejemplo: nombre@dominio.com.") from error
    return correo.normalized.lower()


def validar_contrasena(valor: str) -> None:
    if not (8 <= len(valor) <= 256
            and any(c.isupper() for c in valor)
            and any(not c.isalnum() and not c.isspace() for c in valor)):
        raise CampoInvalido("contrasena", "Usa de 8 a 256 caracteres, con al menos una mayúscula y un símbolo.")