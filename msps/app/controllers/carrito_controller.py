# ======================================================================
# QUÉ HACE
#   El carrito y el pago. API en JSON: GET /api/verificar-login, GET
#   /api/carrito/cantidad, POST /api/carrito/agregar, /actualizar y /eliminar.
#   Páginas: GET /carrito y GET /checkout.
# HASTA DÓNDE LLEGA (y qué NO hace)
#   Valida la petición y la sesión. No sabe dónde se guarda el carrito (eso lo decide
#   el repositorio). OJO: /checkout solo muestra la página; todavía NO crea
#   alquileres ni facturas.
# ======================================================================
"""
Controlador del carrito de compras.

Principio SOLID aplicado: SRP + DIP. Este controlador solo orquesta
HTTP (valida lo que llega, verifica sesión de usuario, decide la
respuesta). No sabe dónde ni cómo se guarda el carrito: eso se lo pide
a un CarritoRepositorioBase que la fábrica (`crear_carrito_repositorio`
en app/factories.py) le entrega. Antes, este archivo leía y escribía
`request.session["carrito"]` directamente; ahora esa responsabilidad
vive en app/repositories/carrito_repository.py.
"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse

from app.models.maquinaria import MaquinariaModel
from app.current_user import obtener_sesion_actual
from app.builders import PageContextBuilder
from app.templating import templates
from app.factories import crear_carrito_repositorio

router = APIRouter()


@router.get("/api/verificar-login")
async def verificar_login(request: Request):
    """Verifica si el usuario está logueado"""
    sesion = obtener_sesion_actual(request)
    return {"logueado": sesion is not None}


@router.get("/api/carrito/cantidad")
async def cantidad_carrito(request: Request):
    """Devuelve cuántas máquinas hay en el carrito (0 si no hay sesión)"""
    sesion = obtener_sesion_actual(request)
    if not sesion:
        return {"cantidad": 0}
    repositorio = crear_carrito_repositorio(request)
    return {"cantidad": repositorio.contar()}


@router.post("/api/carrito/agregar")
async def agregar_carrito(request: Request, data: dict):
    """Agrega una máquina al carrito (o actualiza sus horas si ya estaba)"""
    sesion = obtener_sesion_actual(request)
    if not sesion:
        raise HTTPException(status_code=401, detail="No estás logueado")

    try:
        id_maquinaria = int(data.get("id_maquinaria"))
        horas = int(data.get("horas", 1))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Datos inválidos")

    if not MaquinariaModel.obtener_por_id(id_maquinaria):
        raise HTTPException(status_code=404, detail="Máquina no encontrada")

    repositorio = crear_carrito_repositorio(request)
    repositorio.agregar(id_maquinaria, horas)

    return {"status": "ok", "mensaje": "Agregado al carrito"}


@router.post("/api/carrito/actualizar")
async def actualizar_carrito(request: Request, data: dict):
    """Actualiza las horas de una máquina que ya está en el carrito"""
    sesion = obtener_sesion_actual(request)
    if not sesion:
        raise HTTPException(status_code=401, detail="No estás logueado")

    try:
        id_maquinaria = int(data.get("id_maquinaria"))
        horas = int(data.get("horas", 1))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Datos inválidos")

    repositorio = crear_carrito_repositorio(request)
    repositorio.actualizar_horas(id_maquinaria, horas)

    return {"status": "ok"}


@router.post("/api/carrito/eliminar")
async def eliminar_carrito(request: Request, data: dict):
    """Elimina una máquina del carrito"""
    sesion = obtener_sesion_actual(request)
    if not sesion:
        raise HTTPException(status_code=401, detail="No estás logueado")

    try:
        id_maquinaria = int(data.get("id_maquinaria"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Datos inválidos")

    repositorio = crear_carrito_repositorio(request)
    repositorio.eliminar(id_maquinaria)

    return {"status": "ok"}


@router.get("/carrito")
async def ver_carrito(request: Request):
    """Muestra el carrito"""
    sesion = obtener_sesion_actual(request)
    if not sesion:
        return RedirectResponse(url="/login?next=/carrito", status_code=302)

    repositorio = crear_carrito_repositorio(request)

    items = []
    for item in repositorio.leer():
        maquina = MaquinariaModel.obtener_por_id(item.id_maquinaria)
        if maquina:
            items.append({"maquina": maquina, "horas": item.horas})

    context = (
        PageContextBuilder()
        .with_title("Mi Carrito")
        .with_active_nav("Buscar Maquina")
        .with_sesion(sesion)
        .build()
    )
    context["carrito"] = items

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
#   - Todas las rutas empiezan con obtener_sesion_actual(request). Sin sesión:
#     agregar, actualizar y eliminar responden 401; verificar-login responde
#     {'logueado': False} y cantidad responde {'cantidad': 0}; /carrito y /checkout
#     redirigen a /login?next=... (OJO: esa dirección todavía no existe como página y
#     devuelve 405; solo existe POST /login).
#   - agregar: convierte id_maquinaria y horas a int (si falla, 400), comprueba con
#     MaquinariaModel.obtener_por_id que la máquina existe (404 si no) y llama
#     repositorio.agregar(id, horas).
#   - ver_carrito: recorre repositorio.leer(), busca cada máquina con
#     MaquinariaModel.obtener_por_id y arma la lista [{maquina, horas}] para
#     carrito.html.
#   - Aviso: agregar_carrito no revisa si la tarifa es 0; el bloqueo 'Solo por
#     cotización' es solo visual (está en detalle_maquina.html).
# USA
#   current_user.py, models/maquinaria.py, factories.crear_carrito_repositorio,
#   builders.py, templating.py.
# DÓNDE SE LLAMA
#   app/__init__.py: include_router(carrito_controller.router).
#   El navegador con fetch(): detalle_maquina.html (/api/verificar-login,
#   /api/carrito/agregar, /api/carrito/cantidad), buscar_maquinas.html
#   (/api/carrito/cantidad) y carrito.html (/api/carrito/eliminar,
#   /api/carrito/actualizar; luego navega a /checkout).
# ======================================================================