from __future__ import annotations

from fastapi import APIRouter, Form, Request
from app.models import registro_verificado
from app.correo import CorreoNoDisponible
from app.builders import PageContextBuilder
from app.templating import templates
from app.current_user import obtener_sesion_actual
from fastapi.responses import RedirectResponse

from app.factories import crear_carrito
from app.models.autenticacion import AutenticacionModel
from app.security import SESSION_COOKIE_NAME, firmar_sesion

router = APIRouter()


def pagina_estado(request, texto, token=None, status=200):
    contexto = PageContextBuilder().with_title("Verificar correo · MSPS").with_sesion(obtener_sesion_actual(request)).build()
    contexto.update(texto=texto, token=token)
    return templates.TemplateResponse(request, "verificar_correo.html", contexto, status_code=status,
                                      headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})


def registrar(request, tipo, nombre, correo, contrasena, documento):
    try:
        registro_verificado.solicitar(tipo, nombre, correo, contrasena, documento)
    except ValueError as error:
        return pagina_estado(request, str(error), status=400)
    except CorreoNoDisponible as error:
        return pagina_estado(request, str(error), status=503)
    return pagina_estado(request, "Revisa tu correo y la carpeta de spam. Abre el enlace y confirma para activar tu cuenta. El enlace vence en 30 minutos.")


@router.post("/registro/persona")
def registrar_persona(request: Request, cedula: str = Form(...), usuario: str = Form(...),
                      correo: str = Form(...), contrasena: str = Form(...)):
    return registrar(request, "persona", usuario, correo, contrasena, cedula)


@router.post("/registro/empresa")
def registrar_empresa(request: Request, nombre_empresa: str = Form(...), nit: str = Form(...),
                      correo: str = Form(...), contrasena: str = Form(...)):
    return registrar(request, "empresa", nombre_empresa, correo, contrasena, nit)


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


