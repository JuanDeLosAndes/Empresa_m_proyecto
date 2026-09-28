"""
Controlador del carrito de compras.
El carrito se guarda en sesión como lista de {"id": int, "horas": int}.
"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse

from app.models.maquinaria import MaquinariaModel
from app.current_user import obtener_sesion_actual
from app.builders import PageContextBuilder
from app.templating import templates

router = APIRouter()


def _leer_carrito(request: Request) -> list:
    """Lee el carrito de la sesión y lo normaliza (acepta el formato viejo de solo IDs)."""
    resultado = []
    for item in request.session.get("carrito", []):
        if isinstance(item, dict):
            resultado.append({
                "id": int(item["id"]),
                "horas": max(1, int(item.get("horas", 1))),
            })
        else:
            resultado.append({"id": int(item), "horas": 1})
    return resultado


def _guardar_carrito(request: Request, carrito: list) -> None:
    # Se reasigna la lista completa para que la sesión siempre detecte el cambio
    request.session["carrito"] = carrito


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
    return {"cantidad": len(_leer_carrito(request))}


@router.post("/api/carrito/agregar")
async def agregar_carrito(request: Request, data: dict):
    """Agrega una máquina al carrito (o actualiza sus horas si ya estaba)"""
    sesion = obtener_sesion_actual(request)
    if not sesion:
        raise HTTPException(status_code=401, detail="No estás logueado")

    try:
        id_maquinaria = int(data.get("id_maquinaria"))
        horas = max(1, int(data.get("horas", 1)))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Datos inválidos")

    if not MaquinariaModel.obtener_por_id(id_maquinaria):
        raise HTTPException(status_code=404, detail="Máquina no encontrada")

    carrito = _leer_carrito(request)
    for item in carrito:
        if item["id"] == id_maquinaria:
            item["horas"] = horas
            break
    else:
        carrito.append({"id": id_maquinaria, "horas": horas})

    _guardar_carrito(request, carrito)
    return {"status": "ok", "mensaje": "Agregado al carrito"}


@router.post("/api/carrito/actualizar")
async def actualizar_carrito(request: Request, data: dict):
    """Actualiza las horas de una máquina que ya está en el carrito"""
    sesion = obtener_sesion_actual(request)
    if not sesion:
        raise HTTPException(status_code=401, detail="No estás logueado")

    try:
        id_maquinaria = int(data.get("id_maquinaria"))
        horas = max(1, int(data.get("horas", 1)))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Datos inválidos")

    carrito = _leer_carrito(request)
    for item in carrito:
        if item["id"] == id_maquinaria:
            item["horas"] = horas
    _guardar_carrito(request, carrito)
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

    carrito = [i for i in _leer_carrito(request) if i["id"] != id_maquinaria]
    _guardar_carrito(request, carrito)
    return {"status": "ok"}


@router.get("/carrito")
async def ver_carrito(request: Request):
    """Muestra el carrito"""
    sesion = obtener_sesion_actual(request)
    if not sesion:
        return RedirectResponse(url="/login?next=/carrito", status_code=302)

    items = []
    for item in _leer_carrito(request):
        maquina = MaquinariaModel.obtener_por_id(item["id"])
        if maquina:
            items.append({"maquina": maquina, "horas": item["horas"]})

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