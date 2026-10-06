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