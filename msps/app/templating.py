
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


class TemplateEngine:
    """Envoltorio Singleton alrededor de Jinja2Templates."""

    _instance: Optional["TemplateEngine"] = None

    def __new__(cls) -> "TemplateEngine":
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
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