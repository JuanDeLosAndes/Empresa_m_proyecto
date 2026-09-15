
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.controllers import home_controller

BASE_DIR = Path(__file__).resolve().parent


def create_app() -> FastAPI:
    """Factory Method: construye y configura la instancia de FastAPI."""
    app = FastAPI(
        title="MSPS - Maquiservicio Pérez SAS",
        description="Plataforma de alquiler de maquinaria pesada.",
    )

    app.mount(
        "/static",
        StaticFiles(directory=str(BASE_DIR / "static")),
        name="static",
    )

    app.include_router(home_controller.router)

    return app