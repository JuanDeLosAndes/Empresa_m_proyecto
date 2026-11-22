from email_validator import EmailNotValidError, validate_email


def validar_correo(valor: str) -> str:
    try:
        correo = validate_email(valor.strip(), check_deliverability=False)
    except EmailNotValidError as error:
        raise ValueError("Escribe un correo válido, por ejemplo nombre@empresa.com.") from error
    return correo.normalized.lower()


def validar_contrasena(valor: str) -> None:
    if not (len(valor) <= 256 and sum(c in "0123456789" for c in valor) >= 8
            and any(c.isupper() for c in valor)
            and any(not c.isalnum() and not c.isspace() for c in valor)):
        raise ValueError("Incluye al menos 8 números, una mayúscula y un símbolo (máximo 256 caracteres).")