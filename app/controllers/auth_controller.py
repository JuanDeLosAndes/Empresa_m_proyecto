# ======================================================================
# QUÉ HACE
#   Controlador de cuentas: registro de persona natural (/registro/persona), registro
#   de empresa (/registro/empresa), inicio de sesión (/login) y cierre (/logout).
# HASTA DÓNDE LLEGA (y qué NO hace)
#   Solo recibe los formularios, le pregunta al Modelo (AutenticacionModel) y responde
#   con la redirección y la cookie de sesión. NO decide si las credenciales son
#   correctas ni conoce SQLite: eso es models/autenticacion.py.
# ======================================================================
from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.factories import crear_carrito
from app.models.autenticacion import AutenticacionModel
from app.security import SESSION_COOKIE_NAME, firmar_sesion

router = APIRouter()


@router.post("/registro/persona")
def registrar_persona(
    cedula: str = Form(...),
    usuario: str = Form(...),
    correo: str = Form(...),
    contrasena: str = Form(...),
):
    creada = AutenticacionModel.registrar_persona(cedula, usuario, correo, contrasena)
    return RedirectResponse(url="/?registro=ok" if creada else "/?registro=error", status_code=303)


@router.post("/registro/empresa")
def registrar_empresa(
    nombre_empresa: str = Form(...),
    nit: str = Form(...),
    correo: str = Form(...),
    contrasena: str = Form(...),
):
    creada = AutenticacionModel.registrar_empresa(nombre_empresa, nit, correo, contrasena)
    return RedirectResponse(url="/?registro=ok" if creada else "/?registro=error", status_code=303)


@router.post("/login")
def login(request: Request, identificador: str = Form(...), contrasena: str = Form(...)):
    credencial = AutenticacionModel.autenticar(identificador, contrasena)
    if credencial is None:
        return RedirectResponse(url="/?login=error", status_code=303)

    respuesta = RedirectResponse(url="/?login=ok", status_code=303)
    respuesta.set_cookie(
        SESSION_COOKIE_NAME,
        firmar_sesion(credencial.tipo, credencial.id),
        httponly=True,
        samesite="lax",
    )
    crear_carrito(request).vaciar()  # cada inicio de sesión empieza con el carrito vacío
    return respuesta


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    respuesta = RedirectResponse(url="/", status_code=303)
    respuesta.delete_cookie(SESSION_COOKIE_NAME)
    return respuesta

# ======================================================================
# CÓMO LO HACE (en concreto)
#   - registrar_*: AutenticacionModel devuelve True/False y el controlador redirige a
#     /?registro=ok o /?registro=error (home_controller muestra el mensaje).
#   - login: AutenticacionModel.autenticar -> Credencial(tipo, id); security.firmar_sesion
#     genera el valor de la cookie 'msps_session' (httponly, samesite=lax).
#   - logout: borra request.session (el carrito) y la cookie de sesión.
# USA
#   app/models/autenticacion.py, app/security.py, app/factories.py (crear_carrito).
# DÓNDE SE LLAMA
#   app/__init__.py: create_app() hace app.include_router(auth_controller.router).
#   Los formularios del navbar (components/auth/*.html) envían a estas rutas.
# ======================================================================

