from __future__ import annotations

from pathlib import Path
from typing import Optional

from starlette.requests import Request
from fastapi.templating import Jinja2Templates
from jinja2 import pass_context


@pass_context
def url_local(context, name, **params):
    """URLs del mismo sitio: evita HTTP mezclado con HTTPS detrás de Azure."""
    return context["request"].url_for(name, **params).path


TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"


def contexto_navegacion(request: Request) -> dict:
    return {"panel_acceso": request.query_params.get("acceso", "")}


class TemplateEngine:
    """Envoltorio Singleton alrededor de Jinja2Templates."""

    _instance: Optional["TemplateEngine"] = None

    def __new__(cls) -> "TemplateEngine":
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._templates = Jinja2Templates(directory=str(TEMPLATES_DIR), context_processors=[contexto_navegacion])
            instance._templates.env.globals["url_for"] = url_local
            cls._instance = instance
        return cls._instance

    @property
    def templates(self) -> Jinja2Templates:
        return self._templates


def get_templates() -> Jinja2Templates:
    """Punto único de acceso al motor de plantillas (Singleton)."""
    return TemplateEngine().templates


# Instancia lista para usar directamente desde los controladores.
templates = get_templates()
