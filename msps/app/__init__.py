
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.controllers import auth_controller, home_controller
from app.database import init_db
from app.seed import seed_demo_data

BASE_DIR = Path(__file__).resolve().parent


def create_app() -> FastAPI:
    """Factory Method: construye y configura la instancia de FastAPI."""
    app = FastAPI(
        title="MSPS - Maquiservicio Pérez SAS",
        description="Plataforma de alquiler de maquinaria pesada.",
    )

    # Crea las tablas si no existen y siembra datos de ejemplo
    # (categorías y máquinas) la primera vez que se levanta la app.
    init_db()
    seed_demo_data()

    app.mount(
        "/static",
        StaticFiles(directory=str(BASE_DIR / "static")),
        name="static",
    )

    app.include_router(home_controller.router)
    app.include_router(auth_controller.router)

    return app