# ======================================================================
# QUÉ HACE
#   Controlador del carrito: API JSON (/api/verificar-login, /api/carrito/cantidad,
#   /agregar, /actualizar, /eliminar) y las páginas /carrito y /checkout.
# HASTA DÓNDE LLEGA (y qué NO hace)
#   Solo lee la petición, valida que los datos sean números, llama al Modelo
#   (CarritoModel) y devuelve JSON o la plantilla. NO calcula totales ni IVA y no
#   consulta máquinas: eso es models/carrito.py. La comprobación de "¿hay sesión?"
#   la hace dependencias.py.
# ======================================================================
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.builders import PageContextBuilder
from app.controllers.dependencias import exigir_sesion
from app.current_user import SesionActual, obtener_sesion_actual
from app.factories import crear_carrito
from app.models.carrito import MaquinaNoEncontrada
from app.templating import templates

router = APIRouter()


def _entero(data: dict, clave: str, por_defecto=None) -> int:
    """Lee un número entero del cuerpo JSON; si no se puede, responde 400."""
    try:
        return int(data.get(clave, por_defecto))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Datos inválidos")


@router.get("/api/verificar-login")
async def verificar_login(request: Request):
    """Verifica si el usuario está logueado"""
    return {"logueado": obtener_sesion_actual(request) is not None}


@router.get("/api/carrito/cantidad")
async def cantidad_carrito(request: Request):
    """Devuelve cuántas máquinas hay en el carrito (0 si no hay sesión)"""
    if obtener_sesion_actual(request) is None:
        return {"cantidad": 0}
    return {"cantidad": crear_carrito(request).contar()}


@router.post("/api/carrito/agregar")
async def agregar_carrito(request: Request, data: dict, _: SesionActual = Depends(exigir_sesion)):
    """Agrega una máquina al carrito (o actualiza sus horas si ya estaba)"""
    id_maquinaria = _entero(data, "id_maquinaria")
    horas = _entero(data, "horas", 1)
    try:
        crear_carrito(request).agregar(id_maquinaria, horas)
    except MaquinaNoEncontrada:
        raise HTTPException(status_code=404, detail="Máquina no encontrada")
    return {"status": "ok", "mensaje": "Agregado al carrito"}


@router.post("/api/carrito/actualizar")
async def actualizar_carrito(request: Request, data: dict, _: SesionActual = Depends(exigir_sesion)):
    """Actualiza las horas de una máquina que ya está en el carrito"""
    crear_carrito(request).actualizar_horas(_entero(data, "id_maquinaria"), _entero(data, "horas", 1))
    return {"status": "ok"}


@router.post("/api/carrito/eliminar")
async def eliminar_carrito(request: Request, data: dict, _: SesionActual = Depends(exigir_sesion)):
    """Elimina una máquina del carrito"""
    crear_carrito(request).eliminar(_entero(data, "id_maquinaria"))
    return {"status": "ok"}


@router.get("/carrito")
async def ver_carrito(request: Request):
    """Muestra el carrito"""
    sesion = obtener_sesion_actual(request)
    if not sesion:
        return RedirectResponse(url="/login?next=/carrito", status_code=302)

    resumen = crear_carrito(request).resumen()
    context = (
        PageContextBuilder()
        .with_title("Mi Carrito")
        .with_active_nav("Buscar Maquina")
        .with_sesion(sesion)
        .build()
    )
    context["carrito"] = resumen.lineas
    context["resumen"] = resumen
    return templates.TemplateResponse(request, "carrito.html", context)


@router.get("/checkout")
async def checkout(request: Request):
    """Página de pago"""
    sesion = obtener_sesion_actual(request)
    if not sesion:
        return RedirectResponse(url="/login?next=/checkout", status_code=302)

    context = (
        PageContextBuilder()
        .with_title("Checkout")
        .with_active_nav("Buscar Maquina")
        .with_sesion(sesion)
        .build()
    )
    return templates.TemplateResponse(request, "checkout.html", context)

# ======================================================================
# CÓMO LO HACE (en concreto)
#   - Las rutas que modifican el carrito usan Depends(exigir_sesion): sin sesión
#     responden 401 antes de entrar a la función.
#   - _entero convierte el JSON a int y responde 400 si no se puede (igual que antes).
#   - agregar: CarritoModel.agregar lanza MaquinaNoEncontrada -> 404.
#   - /carrito: CarritoModel.resumen() devuelve las líneas y los totales; la plantilla
#     solo los pinta.
# USA
#   app/models/carrito.py, app/controllers/dependencias.py, app/factories.py
#   (crear_carrito), app/builders.py, app/current_user.py, app/templating.py.
# DÓNDE SE LLAMA
#   app/__init__.py: create_app() hace app.include_router(carrito_controller.router).
#   El JavaScript de detalle_maquina.html y carrito.html llama a /api/carrito/*.
# ======================================================================

