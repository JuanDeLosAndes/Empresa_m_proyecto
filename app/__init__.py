from pathlib import Path
import time

from dotenv import load_dotenv

# Lee la configuración local antes de inicializar la conexión y la clave de sesión.
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.controllers import (
    admin_controller,
    auth_controller,
    carrito_controller,
    home_controller,
    media_controller,
)
from app.controllers import afiliacion_controller, cotizacion_controller, pago_controller, diagnostico_controller
from app.database import init_db
from app.seed import seed_demo_data
from app.security import SECRET_KEY

BASE_DIR = Path(__file__).resolve().parent


def create_app() -> FastAPI:
    """Factory Method: construye y configura la instancia de FastAPI."""
    app = FastAPI(
        title="MSPS - Maquiservicio Pérez SAS",
        description="Plataforma de alquiler de maquinaria pesada.",
    )

    @app.middleware("http")
    async def medir_tiempo(request, call_next):
        inicio = time.perf_counter()
        respuesta = await call_next(request)
        respuesta.headers["Server-Timing"] = f"app;dur={(time.perf_counter() - inicio) * 1000:.1f}"
        return respuesta

    # SessionMiddleware
    app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

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
    app.include_router(admin_controller.router)
    app.include_router(afiliacion_controller.router)
    app.include_router(cotizacion_controller.router)

    app.include_router(pago_controller.router)

    app.include_router(diagnostico_controller.router)

    return app