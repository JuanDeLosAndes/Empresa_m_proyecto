"""
Controlador (la C de MVC) de las rutas públicas del home de MSPS.

El controlador solo orquesta: le pide al Builder el contexto de la
página y se lo entrega al motor de plantillas (Singleton). No conoce
los detalles de cómo se arma cada formulario ni cómo se configura Jinja.
"""
from fastapi import APIRouter, Request

from app.builders import PageContextBuilder
from app.templating import templates

router = APIRouter()


@router.get("/")
def home(request: Request):
    context = (
        PageContextBuilder()
        .with_title("MSPS · Alquiler de Maquinaria Pesada")
        .with_active_nav("Inicio")
        .with_hero(
            headline_lines=["ALQUILER", "MAQUINARIA", "PESADA."],
            subtitle="Servicio y alquiler de equipos de excavación para toda Bogotá.",
        )
        .with_auth_forms()
        .with_categories()
        .build()
    )
    return templates.TemplateResponse(request, "index.html", context)


@router.get("/maquinas")
def buscar_maquinas(request: Request):
    context = (
        PageContextBuilder()
        .with_title("MSPS · Buscar Máquinas")
        .with_active_nav("Máquinas")
        .build()
    )
    return templates.TemplateResponse(request, "buscar_maquinas.html", context)


@router.get("/maquina/{id}")
def detalle_maquina(request: Request, id: int):
    context = (
        PageContextBuilder()
        .with_title("MSPS · Detalle de Máquina")
        .with_active_nav("Máquinas")
        .build()
    )
    return templates.TemplateResponse(request, "detalle_maquina.html", context)