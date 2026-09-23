"""
Fábrica de formularios de autenticación de MSPS.

Patrón creacional aplicado: FACTORY METHOD.
Según el tipo de registro solicitado ("persona_natural" o "empresa") se
construye el conjunto de campos correspondiente. Ni las plantillas ni el
controlador necesitan conocer las reglas de cada tipo de cuenta: solo le
piden a la fábrica el "producto" (lista de campos) que corresponde.
Agregar un tercer tipo de cuenta en el futuro (p. ej. "operador") solo
implica sumar un caso aquí, sin tocar vistas ni controladores.

Nota: el `name` de cada campo debe coincidir con el parámetro que
recibe la ruta POST correspondiente en app/controllers/auth_controller.py,
que a su vez lo pasa a app/models/usuario.py o app/models/empresa.py.
El formulario de empresa antes tenía un campo "usuario" que no existía
en ninguna columna real de la tabla `empresas`; se reemplazó por
"correo" (que sí es una columna del diagrama) porque además es lo que
se usa para iniciar sesión como empresa.
"""
from __future__ import annotations

from typing import Literal, TypedDict

TipoRegistro = Literal["persona_natural", "empresa"]


class CampoFormulario(TypedDict):
    name: str
    label: str
    type: str
    placeholder: str


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
            {"name": "contrasena", "label": "Contraseña", "type": "password", "placeholder": "Contraseña"},
        ]

    @staticmethod
    def build_register_fields(tipo: TipoRegistro) -> list[CampoFormulario]:
        if tipo == "persona_natural":
            return [
                {"name": "cedula", "label": "Cédula", "type": "text", "placeholder": "Cédula"},
                {"name": "usuario", "label": "Usuario", "type": "text", "placeholder": "Usuario"},
                {"name": "correo", "label": "Correo electrónico", "type": "email", "placeholder": "Correo electrónico"},
                {"name": "contrasena", "label": "Contraseña", "type": "password", "placeholder": "Contraseña"},
            ]
        if tipo == "empresa":
            return [
                {"name": "nombre_empresa", "label": "Nombre de la Empresa", "type": "text", "placeholder": "Nombre de la Empresa"},
                {"name": "nit", "label": "NIT", "type": "text", "placeholder": "NIT"},
                {"name": "correo", "label": "Correo electrónico", "type": "email", "placeholder": "Correo electrónico"},
                {"name": "contrasena", "label": "Contraseña", "type": "password", "placeholder": "Contraseña"},
            ]
        raise ValueError(f"Tipo de registro no soportado: {tipo}")