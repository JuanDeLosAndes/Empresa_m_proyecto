from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from app.views.builders import PageContextBuilder
from app.controllers.dependencias import exigir_sesion
from app.models import afiliacion
from app.views.templating import templates

router = APIRouter()


def persona(sesion=Depends(exigir_sesion)):
    if sesion["tipo"] != "persona_natural":
        raise HTTPException(403, "Se requiere una cuenta personal")
    return sesion


def empresa(sesion=Depends(exigir_sesion)):
    if sesion["tipo"] != "empresa":
        raise HTTPException(403, "Se requiere una cuenta de empresa")
    return sesion


class Destino(BaseModel):
    id_empresa: int = Field(gt=0)


class Decision(BaseModel):
    aceptar: bool


def ejecutar(operacion, *args):
    try:
        operacion(*args)
    except afiliacion.RegistroNoEncontrado as error:
        raise HTTPException(404, str(error))
    except afiliacion.SolicitudEnConflicto as error:
        raise HTTPException(409, str(error))
    return {"status": "ok"}


@router.get("/mi-empresa")
def panel(request: Request, sesion=Depends(exigir_sesion)):
    if sesion["tipo"] == "empresa":
        datos = afiliacion.panel_empresa(sesion["id"])
    elif sesion["tipo"] == "persona_natural":
        datos = afiliacion.panel_persona(sesion["id"])
    else:
        raise HTTPException(403, "Se requiere una cuenta personal o de empresa")
    contexto = PageContextBuilder().with_title("Mi empresa · MSPS").with_sesion(sesion).build()
    return templates.TemplateResponse(request, "mi_empresa.html", {**contexto, **datos})


@router.post("/api/empresa/solicitudes", status_code=201)
def solicitar(datos: Destino, sesion=Depends(persona)):
    return ejecutar(afiliacion.solicitar, sesion["id"], datos.id_empresa)


@router.patch("/api/empresa/solicitudes/{id_usuario}")
def resolver(id_usuario: int, datos: Decision, sesion=Depends(empresa)):
    return ejecutar(afiliacion.resolver, sesion["id"], id_usuario, datos.aceptar)


@router.delete("/api/empresa/integrantes/{id_usuario}")
def retirar(id_usuario: int, sesion=Depends(empresa)):
    return ejecutar(afiliacion.retirar, sesion["id"], id_usuario)