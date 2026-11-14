#!/bin/sh
PORT=${PORT:-8000}
echo "=========================================="
echo "🚀 Iniciando FastAPI en el puerto $PORT"
echo "📁 Archivo principal: main.py"
echo "🔧 Instancia de FastAPI: app"
echo "=========================================="
# Los workers comparten una clave incluso en un arranque local sin configuración.
export MSPS_SECRET_KEY="${MSPS_SECRET_KEY:-$(python -c 'import secrets; print(secrets.token_hex(32))')}"
exec gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:$PORT