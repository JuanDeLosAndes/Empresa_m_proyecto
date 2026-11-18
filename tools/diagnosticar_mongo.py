import os
import sys
import time
from urllib.parse import urlsplit

from dotenv import load_dotenv
import pymongo
from pymongo.errors import ConfigurationError, OperationFailure, PyMongoError, ServerSelectionTimeoutError

load_dotenv()
uri = os.environ.get("MONGODB_URI", "").strip()
if not uri:
    raise SystemExit("Falta MONGODB_URI. Configúrala en .env o en las variables de Azure.")
try:
    host = urlsplit(uri).hostname
    print("Servidor:", host, "| Base:", os.environ.get("MONGODB_DB", "msps"))
    inicio = time.perf_counter()
    with pymongo.MongoClient(uri, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000) as cliente:
        with pymongo.timeout(5):
            cliente.admin.command("ping")
            db = cliente[os.environ.get("MONGODB_DB", "msps")]
            print("Máquinas:", db.maquinas.count_documents({}))
            print("Fotos GridFS:", db["fs.files"].count_documents({}))
            print("Bloques GridFS:", db["fs.chunks"].count_documents({}))
    print(f"Conexión correcta. Diagnóstico completo: {(time.perf_counter()-inicio)*1000:.0f} ms")
except OperationFailure:
    sys.exit("MongoDB respondió, pero rechazó el usuario o los permisos. Revisa el usuario de base de datos.")
except ServerSelectionTimeoutError:
    sys.exit("No hay conexión: revisa IPs de salida de Azure autorizadas en Atlas, DNS, firewall y estado del servidor.")
except (ConfigurationError, ValueError):
    sys.exit("La URI o el DNS no son válidos. Copia la URI Drivers/Python y codifica caracteres especiales de la contraseña.")
except PyMongoError:
    sys.exit("MongoDB no respondió correctamente. Revisa TLS, red y nombre de la base.")