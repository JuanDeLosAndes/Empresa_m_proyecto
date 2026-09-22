"""
Controlador (la C de MVC) de autenticación de MSPS.

Solo orquesta: recibe lo que llegó del formulario, se lo pasa al
Modelo correspondiente (UsuarioModel / EmpresaModel) y decide la
respuesta HTTP (redirección + cookie de sesión). No arma HTML y no
contiene SQL: eso vive en app/models/.

Administrador no tiene un formulario público de registro a propósito
(ver app/models/usuario.py): solo se crea desde app/seed.py o desde
consola, nunca desde una ruta expuesta a cualquier visitante.
"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Form
from fastapi.responses import RedirectResponse

from app.models.usuario import UsuarioModel
from app.models.empresa import EmpresaModel
from app.security import firmar_sesion, SESSION_COOKIE_NAME

router = APIRouter()


@router.post("/registro/persona")
def registrar_persona(
    cedula: str = Form(...),
    usuario: str = Form(...),
    correo: str = Form(...),
    contrasena: str = Form(...),
):
    try:
        nuevo = UsuarioModel.crear_cliente(
            nombre=usuario,
            contrasena=contrasena,
            cedula=cedula,
            correo=correo,
        )
    except sqlite3.IntegrityError:
        # Cédula o correo ya registrados
        return RedirectResponse(url="/?registro=error", status_code=303)

    respuesta = RedirectResponse(url="/?registro=ok", status_code=303)
    respuesta.set_cookie(
        SESSION_COOKIE_NAME,
        firmar_sesion(nuevo.rol, nuevo.id_usuario),
        httponly=True,
        samesite="lax",
    )
    return respuesta


@router.post("/registro/empresa")
def registrar_empresa(
    nombre_empresa: str = Form(...),
    nit: str = Form(...),
    correo: str = Form(...),
    contrasena: str = Form(...),
):
    try:
        nueva = EmpresaModel.crear(
            nombre=nombre_empresa,
            nit=nit,
            correo=correo,
            contrasena=contrasena,
        )
    except sqlite3.IntegrityError:
        # NIT o correo ya registrados
        return RedirectResponse(url="/?registro=error", status_code=303)

    respuesta = RedirectResponse(url="/?registro=ok", status_code=303)
    respuesta.set_cookie(
        SESSION_COOKIE_NAME,
        firmar_sesion("empresa", nueva.id_empresa),
        httponly=True,
        samesite="lax",
    )
    return respuesta


@router.post("/login")
def login(identificador: str = Form(...), contrasena: str = Form(...)):
    # El campo "Usuario" del formulario acepta nombre, correo o cédula
    # (personas/administradores) o correo/NIT (empresas): se prueba
    # primero contra Usuario y luego contra Empresa.
    usuario = UsuarioModel.autenticar(identificador, contrasena)
    if usuario:
        respuesta = RedirectResponse(url="/?login=ok", status_code=303)
        respuesta.set_cookie(
            SESSION_COOKIE_NAME,
            firmar_sesion(usuario.rol, usuario.id_usuario),
            httponly=True,
            samesite="lax",
        )
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
        return respuesta

    return RedirectResponse(url="/?login=error", status_code=303)


@router.post("/logout")
def logout():
    respuesta = RedirectResponse(url="/", status_code=303)
    respuesta.delete_cookie(SESSION_COOKIE_NAME)
    return respuesta