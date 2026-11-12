
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.models.usuario import UsuarioModel
from app.models.empresa import EmpresaModel
from app.security import firmar_sesion, SESSION_COOKIE_NAME
from app.factories import crear_carrito_repositorio

router = APIRouter()


@router.post("/registro/persona")
def registrar_persona(
    cedula: str = Form(...),
    usuario: str = Form(...),
    correo: str = Form(...),
    contrasena: str = Form(...),
):
    try:
        UsuarioModel.crear_persona_natural(
            nombre=usuario,
            contrasena=contrasena,
            cedula=cedula,
            correo=correo,
        )
    except sqlite3.IntegrityError:
        return RedirectResponse(url="/?registro=error", status_code=303)
    return RedirectResponse(url="/?registro=ok", status_code=303)


@router.post("/registro/empresa")
def registrar_empresa(
    nombre_empresa: str = Form(...),
    nit: str = Form(...),
    correo: str = Form(...),
    contrasena: str = Form(...),
):
    try:
        EmpresaModel.crear(
            nombre=nombre_empresa,
            nit=nit,
            correo=correo,
            contrasena=contrasena,
        )
    except sqlite3.IntegrityError:
        return RedirectResponse(url="/?registro=error", status_code=303)

    return RedirectResponse(url="/?registro=ok", status_code=303)


@router.post("/login")
def login(request: Request, identificador: str = Form(...), contrasena: str = Form(...)):
    usuario = UsuarioModel.autenticar(identificador, contrasena)
    if usuario:
        respuesta = RedirectResponse(url="/?login=ok", status_code=303)
        respuesta.set_cookie(
            SESSION_COOKIE_NAME,
            firmar_sesion(usuario.rol, usuario.id_usuario),
            httponly=True,
            samesite="lax",
        )
        crear_carrito_repositorio(request).vaciar()  
        return respuesta

    empresa = EmpresaModel.autenticar(identificador, contrasena)
    if empresa:
        respuesta = RedirectResponse(url="/?login=ok", status_code=303)
        respuesta.set_cookie(
            SESSION_COOKIE_NAME,
            firmar_sesion("empresa", empresa.id_empresa),
            httponly=True,
            samesite="lax",
        )
        crear_carrito_repositorio(request).vaciar()  
        return respuesta

    return RedirectResponse(url="/?login=error", status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()  
    respuesta = RedirectResponse(url="/", status_code=303)
    respuesta.delete_cookie(SESSION_COOKIE_NAME)
    return respuesta

