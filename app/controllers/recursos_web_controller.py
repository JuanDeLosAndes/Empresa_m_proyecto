from fastapi import APIRouter, HTTPException, Request, Response

from app.factories import leer_imagen_web
from app.models.recursos_web import RECURSOS, RecursoWebNoDisponible

router = APIRouter()


@router.get("/static/images/{ruta:path}", name="recurso_web")
@router.head("/static/images/{ruta:path}", include_in_schema=False)
def recurso_web(ruta: str, request: Request) -> Response:
    recurso = RECURSOS.get(ruta)
    if recurso is None:
        raise HTTPException(404, "Imagen desconocida.")
    try:
        contenido = leer_imagen_web(recurso)
    except RecursoWebNoDisponible:
        raise HTTPException(503, "Imagen temporalmente no disponible.", headers={
            "Cache-Control": "no-store", "Retry-After": "15",
        }) from None
    etag = f'"{recurso.sha256}"'
    headers = {"ETag": etag, "Cache-Control": "public, max-age=3600",
               "X-Content-Type-Options": "nosniff"}
    candidatos = request.headers.get("if-none-match", "").split(",")
    if any(valor.strip().removeprefix("W/") in ("*", etag) for valor in candidatos):
        return Response(status_code=304, headers=headers)
    headers["Content-Length"] = str(len(contenido))
    return Response(content=b"" if request.method == "HEAD" else contenido,
                    headers=headers, media_type=recurso.tipo)