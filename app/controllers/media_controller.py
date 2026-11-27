from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.factories import crear_imagenes_repositorio
from app.models.almacen import AlmacenNoDisponible
from app.documentos.imagen import ImagenesLector

router = APIRouter()


@router.get("/media/maquinas/{archivo:path}", name="imagen_maquina")
def imagen_maquina(
    archivo: str,
    request: Request,
    imagenes: ImagenesLector = Depends(crear_imagenes_repositorio),
) -> Response:
    try:
        imagen = imagenes.obtener(archivo)
    except AlmacenNoDisponible:
        raise HTTPException(
            status_code=503,
            detail="Imagen temporalmente no disponible.",
            headers={"Cache-Control": "no-store", "Retry-After": "15"},
        ) from None
    if imagen is None:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")

    etag = f'"{imagen.sha256}"'
    cabeceras = {"ETag": etag, "Cache-Control": "public, max-age=86400"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=cabeceras)
    return Response(content=imagen.contenido, media_type=imagen.tipo_contenido, headers=cabeceras)
