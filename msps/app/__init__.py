from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.controllers import auth_controller, home_controller, carrito_controller, media_controller
from app.database import init_db
from app.seed import seed_demo_data

BASE_DIR = Path(__file__).resolve().parent


def create_app() -> FastAPI:
    """Factory Method: construye y configura la instancia de FastAPI."""
    app = FastAPI(
        title="MSPS - Maquiservicio Pérez SAS",
        description="Plataforma de alquiler de maquinaria pesada.",
    )

    # SessionMiddleware
    app.add_middleware(SessionMiddleware, secret_key="tu-secret-key-super-seguro-cambiar-en-produccion")

    # Crea las tablas si no existen y siembra datos de ejemplo
    init_db()
    seed_demo_data()

    app.mount(
        "/static",
        StaticFiles(directory=str(BASE_DIR / "static")),
        name="static",
    )

    app.include_router(home_controller.router)
    app.include_router(auth_controller.router)
    app.include_router(carrito_controller.router)
    app.include_router(media_controller.router)

    return app