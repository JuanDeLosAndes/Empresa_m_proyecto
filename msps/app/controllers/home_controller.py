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
        .build()
    )
    return templates.TemplateResponse(request, "index.html", context)