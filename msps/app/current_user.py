"""
Resuelve quién está autenticado en la sesión actual a partir de la
cookie firmada. Usado por los Controladores para decidir qué le pasan
a la plantilla (por ejemplo, el nombre en la barra de navegación).

No es parte de app/security.py a propósito: security.py es una
utilidad de criptografía pura (no conoce los Modelos); este módulo sí
combina esa utilidad con los Modelos para responder una pregunta de
negocio ("¿quién hizo esta petición?"), así que vive un nivel más
arriba, junto a los controladores que lo consumen.
"""
from __future__ import annotations

from typing import Optional, TypedDict

from fastapi import Request

from app.security import leer_sesion, SESSION_COOKIE_NAME
from app.models.usuario import UsuarioModel
from app.models.empresa import EmpresaModel


class SesionActual(TypedDict):
    tipo: str  # 'cliente' | 'administrador' | 'empresa'
    id: int
    nombre: str


def obtener_sesion_actual(request: Request) -> Optional[SesionActual]:
    datos = leer_sesion(request.cookies.get(SESSION_COOKIE_NAME))
    if not datos:
        return None
    tipo, id_ = datos

    if tipo == "empresa":
        empresa = EmpresaModel.obtener_por_id(id_)
        if not empresa:
            return None
        return {"tipo": "empresa", "id": empresa.id_empresa, "nombre": empresa.nombre}

    usuario = UsuarioModel.obtener_por_id(id_)
    if not usuario or usuario.rol != tipo:
        return None
    return {"tipo": usuario.rol, "id": usuario.id_usuario, "nombre": usuario.nombre}