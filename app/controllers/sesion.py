from __future__ import annotations

from typing import Optional, TypedDict

from fastapi import Request

from app.security import leer_sesion, SESSION_COOKIE_NAME
from app.models.usuario import UsuarioModel
from app.models.empresa import EmpresaModel


class SesionActual(TypedDict):
    tipo: str  # 'persona_natural' | 'administrador' | 'empresa'
    id: int
    nombre: str
    correo: str | None


def obtener_sesion_actual(request: Request) -> Optional[SesionActual]:
    datos = leer_sesion(request.cookies.get(SESSION_COOKIE_NAME))
    if not datos:
        return None
    tipo, id_ = datos

    if tipo == "empresa":
        empresa = EmpresaModel.obtener_por_id(id_)
        if not empresa:
            return None
        return {"tipo": "empresa", "id": empresa.id_empresa, "nombre": empresa.nombre, "correo": empresa.correo}

    usuario = UsuarioModel.obtener_por_id(id_)
    if not usuario or usuario.rol != tipo:
        return None
    return {"tipo": usuario.rol, "id": usuario.id_usuario, "nombre": usuario.nombre, "correo": usuario.correo}