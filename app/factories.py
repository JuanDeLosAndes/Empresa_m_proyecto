
from __future__ import annotations

from typing import Literal, TypedDict

from fastapi import Request

from app.documentos.store import get_mongo_database
from app.repositories.carrito_repository import (
    CarritoRepositorioBase,
    CarritoRepositorioSesion,
)
from app.repositories.candado_repository import CandadoMongo
from app.repositories.imagen_maquina_repository import ImagenesGridFS
from app.repositories.maquina_documentos_repository import MaquinaDocumentosMongo

TipoRegistro = Literal["persona_natural", "empresa"]


def crear_carrito_repositorio(request: Request) -> CarritoRepositorioBase:
    """Factory Method: centraliza qué implementación de carrito se usa.

    Hoy siempre es CarritoRepositorioSesion. Si el carrito debe
    sobrevivir más allá de la sesión (por ejemplo, guardado en base de
    datos ligado al usuario), esta es la única función que cambia;
    ningún controlador necesita tocarse.
    """
    return CarritoRepositorioSesion(request)


def crear_maquina_documentos_repositorio() -> MaquinaDocumentosMongo:
    """Factory Method: centraliza qué implementación del repositorio de
    documentos (ficha técnica + referencias a imágenes) usa la app.

    Hoy es MongoDB sobre el Singleton MongoConnection. Controladores y seed
    reciben el resultado tipado como las interfaces
    MaquinaDocumentosLector / MaquinaDocumentosEscritor.
    """
    return MaquinaDocumentosMongo(get_mongo_database())


def crear_imagenes_repositorio() -> ImagenesGridFS:
    """Factory Method: repositorio de los bytes de las fotos (GridFS de MongoDB)."""
    return ImagenesGridFS(get_mongo_database())


def crear_candado_repositorio() -> CandadoMongo:
    """Factory Method: candado distribuido (en MongoDB) para el seed."""
    return CandadoMongo(get_mongo_database())


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

