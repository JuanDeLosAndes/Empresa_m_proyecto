#!/bin/sh
set -eu
export MSPS_DB_PATH="${MSPS_DB_PATH:-/home/data/msps.db}"
python tools/preparar_sqlite.py
exec python -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1