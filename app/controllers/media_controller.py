# ======================================================================
# QUÉ HACE
#   Entrega las fotos de las máquinas leyéndolas de MongoDB: GET
#   /media/maquinas/{archivo}.
# HASTA DÓNDE LLEGA (y qué NO hace)
#   Solo LEE los bytes y los devuelve como imagen. No sube fotos (eso lo hace
#   seed.py) y no decide qué foto va en cada página (eso lo hacen las plantillas).
# ======================================================================
"""
Controlador que sirve las fotos de las máquinas DESDE MongoDB (GridFS).

El navegador pide /media/maquinas/<slug>/<NN>.jpg y este controlador lee los
bytes de la base. Depende solo de la interfaz `ImagenesLector` (ISP/DIP).
`archivo` es únicamente una clave de búsqueda en GridFS, nunca una ruta del
disco, así que no hay riesgo de recorrido de directorios.
"""
from fastapi import APIRouter, HTTPException, Request, Response

from app.factories import crear_imagenes_repositorio

router = APIRouter()


@router.get("/media/maquinas/{archivo:path}", name="imagen_maquina")
def imagen_maquina(archivo: str, request: Request) -> Response:
    imagen = crear_imagenes_repositorio().obtener(archivo)
    if imagen is None:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")

    etag = f'"{imagen.sha256}"'
    cabeceras = {"ETag": etag, "Cache-Control": "public, max-age=86400"}
    # El navegador ya tiene esta versión: se evita reenviar los bytes.
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=cabeceras)
    return Response(content=imagen.contenido, media_type=imagen.tipo_contenido, headers=cabeceras)

# ======================================================================
# CÓMO LO HACE (en concreto)
#   - crear_imagenes_repositorio().obtener(archivo): si devuelve None, responde 404.
#   - Arma un ETag con el sha256 de la foto. Si el navegador manda If-None-Match
#     igual, responde 304 sin bytes; si no, Response(content,
#     media_type='image/jpeg') con Cache-Control max-age=86400.
#   - La ruta tiene name='imagen_maquina', por eso las plantillas pueden usar
#     url_for('imagen_maquina', archivo=...). `archivo` es solo una clave de búsqueda
#     en GridFS, no una ruta del disco.
# USA
#   factories.crear_imagenes_repositorio -> repositories/imagen_maquina_repository.py
#   (GridFS).
# DÓNDE SE LLAMA
#   app/__init__.py: include_router(media_controller.router).
#   El navegador, cada vez que carga un <img src='/media/maquinas/...'> (portada,
#   listado, detalle).
# ======================================================================
