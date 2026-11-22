from pymongo.errors import PyMongoError

from app.documentos.store import ejecutar_mongo
from app.models.recursos_web import RecursoWeb, RecursoWebNoDisponible


class RecursosWebMongo:
    """Un documento por archivo optimizado. La clave es la huella de sus bytes."""

    def __init__(self, base):
        self.coleccion = base["recursos_web"]

    def guardar(self, recurso: RecursoWeb, contenido: bytes) -> None:
        recurso.comprobar(contenido)
        documento = {"_id": recurso.sha256, "tipo": recurso.tipo, "contenido": contenido}
        ejecutar_mongo(lambda: self.coleccion.replace_one(
            {"_id": recurso.sha256}, documento, upsert=True
        ))

    def leer(self, recurso: RecursoWeb) -> bytes:
        try:
            documento = ejecutar_mongo(lambda: self.coleccion.find_one({"_id": recurso.sha256}))
        except PyMongoError as error:
            raise RecursoWebNoDisponible("MongoDB no está disponible.") from error
        if not documento or documento.get("tipo") != recurso.tipo:
            raise RecursoWebNoDisponible(f"Revisa la importación de {recurso.paquete}.")
        contenido = documento.get("contenido")
        if not isinstance(contenido, bytes):
            raise RecursoWebNoDisponible(f"Faltan los bytes de {recurso.paquete}.")
        recurso.comprobar(contenido)
        return contenido