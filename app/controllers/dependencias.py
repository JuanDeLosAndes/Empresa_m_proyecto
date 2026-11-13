
from __future__ import annotations

from fastapi import HTTPException, Request

from app.current_user import SesionActual, obtener_sesion_actual


def exigir_sesion(request: Request) -> SesionActual:
    sesion = obtener_sesion_actual(request)
    if sesion is None:
        raise HTTPException(status_code=401, detail="No estás logueado")
    return sesion


def exigir_admin(request: Request) -> SesionActual:
    sesion = obtener_sesion_actual(request)
    if sesion is None:
        raise HTTPException(status_code=303, headers={"Location": "/"})  # sin sesión -> inicio
    if sesion["tipo"] != "administrador":
        raise HTTPException(status_code=403, detail="Solo para administradores")
    return sesion

