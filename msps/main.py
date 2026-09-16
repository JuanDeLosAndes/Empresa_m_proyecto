from app import create_app

# Instancia de FastAPI que gunicorn/uvicorn usan como punto de entrada
# (main:app), ahora construida con el Factory Method real de la app
# en vez del stub de ejemplo.
app = create_app()