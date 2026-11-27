from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from app.views.builders import PageContextBuilder
from app.controllers.dependencias import exigir_sesion
from app.controllers.sesion import SesionActual, obtener_sesion_actual
from app.factories import crear_carrito, crear_catalogo_fotos
from app.models.carrito import CarritoModel, MaquinaNoEncontrada, RequiereCotizacion, MaquinaNoDisponible
from pydantic import BaseModel, Field
from app.views.templating import templates

router = APIRouter()
CarritoActual = Annotated[CarritoModel, Depends(crear_carrito)]


class Horas(BaseModel):
    horas: int = Field(ge=1)


class ItemId(BaseModel):
    id_maquinaria: int = Field(gt=0)


class ItemNuevo(ItemId):
    horas: int = Field(default=1, ge=1)


@router.get("/api/maquinas/{id_maquinaria}/estimacion")
def estimar(id_maquinaria: int, carrito: CarritoActual, horas: int = Query(ge=1, le=2_147_483_647)):
    try:
        linea = carrito.estimar(id_maquinaria, horas)
    except MaquinaNoEncontrada:
        raise HTTPException(404, "Máquina no encontrada") from None
    except (RequiereCotizacion, MaquinaNoDisponible) as error:
        raise HTTPException(409, str(error)) from None
    return {"horas": linea.horas, "total_linea": linea.total}


@router.get("/api/verificar-login")
def verificar_login(request: Request):
    """Verifica si el usuario está logueado"""
    return {"logueado": obtener_sesion_actual(request) is not None}


@router.get("/api/carrito/cantidad")
def cantidad_carrito(request: Request, carrito: CarritoActual):
    """Devuelve cuántas máquinas hay en el carrito (0 si no hay sesión)"""
    if obtener_sesion_actual(request) is None:
        return {"cantidad": 0}
    return {"cantidad": carrito.contar()}


@router.post("/api/carrito/agregar", include_in_schema=False)
@router.post("/api/carrito/items", responses={409: {"description": "Requiere cotización"}})
def agregar_carrito(data: ItemNuevo, carrito: CarritoActual, _: SesionActual = Depends(exigir_sesion)):
    try:
        carrito.agregar(data.id_maquinaria, data.horas)
    except MaquinaNoEncontrada:
        raise HTTPException(404, "Máquina no encontrada")
    except (RequiereCotizacion, MaquinaNoDisponible) as error:
        raise HTTPException(409, str(error))
    return {"status": "ok", "mensaje": "Agregado al carrito"}


@router.patch("/api/carrito/items/{id_maquinaria}")
def actualizar_carrito(id_maquinaria: int, data: Horas, carrito: CarritoActual, _: SesionActual = Depends(exigir_sesion)):
    try:
        carrito.actualizar_horas(id_maquinaria, data.horas)
    except MaquinaNoEncontrada:
        raise HTTPException(404, "Máquina no encontrada en el carrito")
    except (RequiereCotizacion, MaquinaNoDisponible) as error:
        raise HTTPException(409, str(error))
    resumen = carrito.resumen()
    linea = next(l for l in resumen.lineas if l.maquina.id_maquinaria == id_maquinaria)
    return {"status": "ok", "horas": linea.horas, "total_linea": linea.total,
            "subtotal": resumen.subtotal, "iva": resumen.iva, "total": resumen.total}


@router.delete("/api/carrito/items/{id_maquinaria}")
def eliminar_carrito(id_maquinaria: int, carrito: CarritoActual, _: SesionActual = Depends(exigir_sesion)):
    carrito.eliminar(id_maquinaria)
    return {"status": "ok"}


@router.post("/api/carrito/actualizar", include_in_schema=False)
def actualizar_anterior(data: ItemNuevo, carrito: CarritoActual, sesion: SesionActual = Depends(exigir_sesion)):
    return actualizar_carrito(data.id_maquinaria, Horas(horas=data.horas), carrito, sesion)


@router.post("/api/carrito/eliminar", include_in_schema=False)
def eliminar_anterior(data: ItemId, carrito: CarritoActual, sesion: SesionActual = Depends(exigir_sesion)):
    return eliminar_carrito(data.id_maquinaria, carrito, sesion)


@router.get("/carrito")
def ver_carrito(request: Request, carrito: CarritoActual):
    """Muestra el carrito"""
    sesion = obtener_sesion_actual(request)
    if not sesion:
        return RedirectResponse(url="/?acceso=login", status_code=302)

    resumen = carrito.resumen()
    context = (
        PageContextBuilder()
        .with_title("Mi Carrito")
        .with_active_nav("Buscar Maquina")
        .with_sesion(sesion)
        .build()
    )
    context["carrito"] = resumen.lineas
    context["resumen"] = resumen
    context["portadas"] = crear_catalogo_fotos().portadas_por_placa() if resumen.lineas else {}
    return templates.TemplateResponse(request, "carrito.html", context)


