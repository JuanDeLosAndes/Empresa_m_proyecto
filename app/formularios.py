"""Campos que el constructor de páginas entrega a las vistas de autenticación."""
from typing import Literal, NotRequired, TypedDict

TipoRegistro = Literal["persona_natural", "empresa"]


class CampoFormulario(TypedDict):
    name: str
    label: str
    type: str
    placeholder: str
    required: NotRequired[bool]


class AuthFormFactory:
    """Crea las listas de campos para los formularios de login y registro."""

    @staticmethod
    def build_login_fields() -> list[CampoFormulario]:
        return [
            {
                "name": "identificador",
                "label": "Usuario",
                "type": "text",
                "placeholder": "Usuario, correo o cédula/NIT",
            },
            {
                "name": "contrasena",
                "label": "Contraseña",
                "type": "password",
                "placeholder": "Contraseña",
            },
        ]

    @staticmethod
    def build_register_fields(tipo: TipoRegistro) -> list[CampoFormulario]:
        if tipo == "persona_natural":
            return [
                {"name": "cedula", "label": "Cédula", "type": "text", "placeholder": "Cédula"},
                {"name": "telefono", "label": "Teléfono (opcional)", "type": "tel", "placeholder": "Teléfono (opcional)", "required": False},
                {"name": "usuario", "label": "Usuario", "type": "text", "placeholder": "Usuario"},
                {"name": "correo", "label": "Correo electrónico", "type": "email", "placeholder": "Correo electrónico"},
                {"name": "contrasena", "label": "Contraseña", "type": "password", "placeholder": "Contraseña"},
            ]
        if tipo == "empresa":
            return [
                {"name": "nombre_empresa", "label": "Nombre de la Empresa", "type": "text", "placeholder": "Nombre de la Empresa"},
                {"name": "direccion", "label": "Dirección (opcional)", "type": "text", "placeholder": "Dirección (opcional)", "required": False},
                {"name": "nit", "label": "NIT", "type": "text", "placeholder": "NIT"},
                {"name": "correo", "label": "Correo electrónico", "type": "email", "placeholder": "Correo electrónico"},
                {"name": "contrasena", "label": "Contraseña", "type": "password", "placeholder": "Contraseña"},
            ]
        raise ValueError(f"Tipo de registro no soportado: {tipo}")