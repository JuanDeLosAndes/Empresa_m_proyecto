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
