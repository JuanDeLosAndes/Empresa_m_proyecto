# ======================================================================
# QUÉ HACE
#   Construye y configura TODA la aplicación FastAPI: activa las sesiones por cookie,
#   prepara SQLite, carga los datos iniciales, publica la carpeta /static y registra
#   las rutas de los 5 controladores.
# HASTA DÓNDE LLEGA (y qué NO hace)
#   Termina cuando devuelve `app`. No tiene lógica de negocio ni rutas propias. El
#   ORDEN importa: primero init_db (crea tablas), luego seed (necesita las tablas), y
#   al final las rutas.
# ======================================================================
from pathlib import Path

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
    app.include_router(admin_controller.router)

    return app

# ======================================================================
# CÓMO LO HACE (en concreto)
#   - FastAPI(...) crea la app.
#   - add_middleware(SessionMiddleware, secret_key=...) hace que `request.session`
#     exista y se guarde en una cookie firmada; ahí vive el carrito.
#   - init_db() crea o migra las tablas; seed_demo_data() carga categorías, máquinas,
#     admin y el catálogo real (SQL + MongoDB).
#   - app.mount('/static', StaticFiles(...)) sirve la carpeta app/static (CSS e
#     imágenes del sitio).
#   - include_router(...) conecta las rutas de home, auth, carrito, media y admin.
# USA
#   fastapi, starlette (SessionMiddleware, StaticFiles)
#   app/database.py (init_db), app/seed.py (seed_demo_data)
#   app/controllers/home_, auth_, carrito_, media_ y admin_controller (sus `router`)
# DÓNDE SE LLAMA
#   main.py (app = create_app()) y los tests (TestClient(create_app())).
# ======================================================================