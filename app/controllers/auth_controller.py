from __future__ import annotations

from fastapi import APIRouter, Form, Request
import logging

from app.models import registro_verificado, recuperacion
from app.services.correo import CorreoNoDisponible, enviar_recuperacion, enviar_verificacion
from app.views.builders import PageContextBuilder
from app.views.templating import templates
from app.controllers.sesion import obtener_sesion_actual
from fastapi.responses import JSONResponse, RedirectResponse

from app.factories import crear_carrito
from app.models.autenticacion import AutenticacionModel
from app.security import SESSION_COOKIE_NAME, firmar_sesion

router = APIRouter()


def respuesta_json(request):
    return "application/json" in request.headers.get("accept", "")


def pagina_estado(request, texto, token=None, status=200, accion="verificar"):
    if respuesta_json(request):
        return JSONResponse({"mensaje": texto}, status_code=status, headers={"Cache-Control": "no-store"})
    contexto = PageContextBuilder().with_title("Verificar correo · MSPS").with_sesion(obtener_sesion_actual(request)).build()
    contexto.update(texto=texto, token=token, accion=accion)
    return templates.TemplateResponse(request, "verificar_correo.html", contexto, status_code=status,
                                      headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})


def registrar(request, tipo, nombre, correo, contrasena, documento, **contacto):
    try:
        registro_verificado.solicitar(tipo, nombre, correo, contrasena, documento, enviar=enviar_verificacion, **contacto)
    except ValueError as error:
        return pagina_estado(request, str(error), status=400)
    except CorreoNoDisponible as error:
        return pagina_estado(request, str(error), status=503)
    return pagina_estado(request, "Revisa tu correo y la carpeta de spam. Abre el enlace y confirma para activar tu cuenta. El enlace vence en 30 minutos.")


@router.post("/registro/persona")
def registrar_persona(request: Request, cedula: str = Form(...), usuario: str = Form(...),
                      correo: str = Form(...), contrasena: str = Form(...), telefono: str = Form("")):
    return registrar(request, "persona", usuario, correo, contrasena, cedula, telefono=telefono)


@router.post("/registro/empresa")
def registrar_empresa(request: Request, nombre_empresa: str = Form(...), nit: str = Form(...),
                      correo: str = Form(...), contrasena: str = Form(...), direccion: str = Form("")):
    return registrar(request, "empresa", nombre_empresa, correo, contrasena, nit, direccion=direccion)


@router.get("/verificar-correo")
def abrir_verificacion(request: Request, token: str = ""):
    return pagina_estado(request, "Confirma tu correo para activar la cuenta.", token=token)


@router.post("/verificar-correo")
def confirmar_correo(request: Request, token: str = Form(...)):
    try:
        registro_verificado.confirmar(token)
    except ValueError as error:
        return pagina_estado(request, str(error), status=400)
    return RedirectResponse("/?registro=ok", status_code=303)


@router.post("/login")
def login(request: Request, identificador: str = Form(...), contrasena: str = Form(...)):
    credencial = AutenticacionModel.autenticar(identificador, contrasena)
    if credencial is None:
        if respuesta_json(request):
            return JSONResponse({"mensaje": "Usuario o contraseña incorrectos."}, status_code=401)
        return RedirectResponse(url="/?login=error", status_code=303)

    respuesta = JSONResponse({"ok": True}) if respuesta_json(request) else RedirectResponse(url="/?login=ok", status_code=303)
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

@router.post("/recuperar")
def solicitar_recuperacion(request: Request, correo: str = Form(...)):
    try:
        recuperacion.solicitar(correo, enviar_recuperacion)
    except ValueError as error:
        return pagina_estado(request, str(error), status=400)
    except CorreoNoDisponible:
        logging.getLogger(__name__).exception("No se pudo entregar el enlace de recuperación")
    return pagina_estado(request, "Si el correo pertenece a una cuenta, recibirás un enlace para cambiar tu contraseña.")


@router.get("/restablecer")
def abrir_recuperacion(request: Request, token: str):
    return pagina_estado(request, "Elige una nueva contraseña.", token, accion="restablecer")


@router.post("/restablecer")
def cambiar_contrasena(request: Request, token: str = Form(...), contrasena: str = Form(...)):
    try:
        recuperacion.confirmar(token, contrasena)
    except ValueError as error:
        return pagina_estado(request, str(error), token, status=400, accion="restablecer")
    return pagina_estado(request, "Tu contraseña se actualizó. Ya puedes iniciar sesión.")

