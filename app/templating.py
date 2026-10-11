# ======================================================================
# QUÉ HACE
#   Crea el motor de plantillas (Jinja2) que convierte los archivos .html de
#   app/templates en páginas completas con datos.
# HASTA DÓNDE LLEGA (y qué NO hace)
#   Solo configura el motor. No arma los datos de la página (eso lo hace builders.py)
#   ni decide qué plantilla se usa (eso lo hace cada controlador).
# ======================================================================

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

# ======================================================================
# CÓMO LO HACE (en concreto)
#   - Singleton: TemplateEngine crea una sola vez
#     Jinja2Templates(directory=app/templates).
#   - Al final del archivo queda la variable lista `templates = get_templates()`.
# USA
#   fastapi.templating.Jinja2Templates.
# DÓNDE SE LLAMA
#   controllers/home_controller.py y controllers/carrito_controller.py, con
#   templates.TemplateResponse(request, 'archivo.html', context).
#   (auth_controller y media_controller no lo usan: solo redirigen o devuelven
#   imágenes.)
# ======================================================================