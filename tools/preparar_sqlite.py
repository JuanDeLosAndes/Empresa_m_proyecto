import os
import sqlite3
from pathlib import Path

raiz = Path(__file__).resolve().parents[1]
origen = raiz / "app" / "msps.db"
destino = Path(os.environ.get("MSPS_DB_PATH", str(origen)))
destino.parent.mkdir(parents=True, exist_ok=True)
if destino.resolve() != origen.resolve() and not destino.exists() and origen.is_file():
    with sqlite3.connect(f"{origen.as_uri()}?mode=ro", uri=True) as fuente:
        with sqlite3.connect(destino) as copia:
            fuente.backup(copia)
    print("Base inicial copiada al almacenamiento persistente.")
else:
    print("Se conserva la base existente o se creará una base nueva.")