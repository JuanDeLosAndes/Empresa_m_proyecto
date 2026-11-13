# ======================================================================
# QUÉ HACE
#   Rutas de la pasarela: iniciar el pago desde el checkout, recibir al cliente
#   de vuelta y confirmar el resultado con la pasarela antes de vaciar el carrito.
# HASTA DÓNDE LLEGA
#   Coordina Modelos (carrito, pagos) y la pasarela. No llama a Wompi directamente.
# ======================================================================
import json
import os
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.builders import PageContextBuilder
from app.controllers.dependencias import exigir_sesion
from app.current_user import SesionActual, obtener_sesion_actual
from app.factories import crear_carrito
from app.models.pago import PagoModel
from app.pagos.fabrica import crear_pasarela_pago
from app.pagos.pasarela import (
    ESTADO_APROBADO,
    ESTADO_PENDIENTE,
    ESTADO_RECHAZADO,
    SolicitudPago,
)
from app.templating import templates

router = APIRouter()


def _base_url() -> str:
    return os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")


def _es_dueno(sesion: SesionActual, pago) -> bool:
    return pago.cliente_tipo == sesion["tipo"] and pago.cliente_id == sesion["id"]


@router.get("/checkout")
async def checkout(request: Request):
    sesion = obtener_sesion_actual(request)
    if not sesion:
        return RedirectResponse(url="/", status_code=302)

    resumen = crear_carrito(request).resumen()
    if not resumen.lineas:
        return RedirectResponse(url="/carrito", status_code=302)

    context = (
        PageContextBuilder()
        .with_title("Checkout")
        .with_active_nav("Buscar Maquina")
        .with_sesion(sesion)
        .build()
    )
    context["resumen"] = resumen
    context["sin_tarifa"] = any(not linea.maquina.costo_por_hora for linea in resumen.lineas)
    return templates.TemplateResponse(request, "checkout.html", context)


@router.post("/api/pagos/iniciar")
async def iniciar_pago(request: Request, sesion: SesionActual = Depends(exigir_sesion)):
    """Crea el pago con el total calculado EN EL SERVIDOR y devuelve la URL de la pasarela."""
    resumen = crear_carrito(request).resumen()
    if not resumen.lineas:
        raise HTTPException(status_code=400, detail="El carrito está vacío")
    if any(not linea.maquina.costo_por_hora for linea in resumen.lineas):
        raise HTTPException(
            status_code=400,
            detail="Hay máquinas sin tarifa publicada. Solicita una cotización antes de pagar.",
        )

    monto = round(resumen.total)
    referencia = f"MSPS-{uuid.uuid4().hex[:16].upper()}"
    detalle = json.dumps(
        [
            {
                "maquina": f"{linea.maquina.marca} {linea.maquina.modelo or ''}".strip(),
                "placa": linea.maquina.placa,
                "horas": linea.horas,
                "subtotal": linea.total,
            }
            for linea in resumen.lineas
        ],
        ensure_ascii=False,
    )

    pasarela = crear_pasarela_pago()
    PagoModel.crear(referencia, sesion["tipo"], sesion["id"], monto, pasarela.nombre, detalle)
    inicio = pasarela.iniciar(
        SolicitudPago(
            referencia=referencia,
            monto_pesos=monto,
            url_retorno=f"{_base_url()}/pago/retorno/{referencia}",
        )
    )
    return {"url": inicio.url_pago}


@router.get("/pago/retorno/{referencia}")
async def retorno_pago(request: Request, referencia: str):
    """El cliente vuelve de la pasarela. Confirmamos el estado con la pasarela, no con la URL."""
    sesion = obtener_sesion_actual(request)
    if not sesion:
        return RedirectResponse(url="/", status_code=302)

    pago = PagoModel.obtener_por_referencia(referencia)
    if pago is None or not _es_dueno(sesion, pago):
        raise HTTPException(status_code=404, detail="Pago no encontrado")

    if pago.estado != ESTADO_APROBADO:
        pasarela = crear_pasarela_pago()
        resultado = pasarela.verificar(referencia, request.query_params.get("id"))
        estado = resultado.estado
        # Si la pasarela cobró otro monto del que mostramos, no lo damos por bueno.
        if estado == ESTADO_APROBADO and resultado.monto_pesos != pago.monto:
            estado = "error"
        PagoModel.actualizar_estado(referencia, estado, resultado.transaccion_id)
        pago = PagoModel.obtener_por_referencia(referencia)

    # Vaciar aquí (y no solo al confirmar) cubre el caso en que el pago ya estaba aprobado.
    if pago.estado == ESTADO_APROBADO:
        crear_carrito(request).vaciar()

    context = (
        PageContextBuilder()
        .with_title("Resultado del pago")
        .with_active_nav("Buscar Maquina")
        .with_sesion(sesion)
        .build()
    )
    context["pago"] = pago
    return templates.TemplateResponse(request, "pago_resultado.html", context)


@router.get("/pago/simulado/{referencia}")
async def pagina_simulada(request: Request, referencia: str):
    """Solo existe con la pasarela simulada: página para aprobar o rechazar el pago de prueba."""
    sesion = obtener_sesion_actual(request)
    if not sesion:
        return RedirectResponse(url="/", status_code=302)
    pago = PagoModel.obtener_por_referencia(referencia)
    if pago is None or not _es_dueno(sesion, pago) or pago.proveedor != "simulada":
        raise HTTPException(status_code=404, detail="Pago no encontrado")

    context = (
        PageContextBuilder()
        .with_title("Pasarela de prueba")
        .with_active_nav("Buscar Maquina")
        .with_sesion(sesion)
        .build()
    )
    context["pago"] = pago
    return templates.TemplateResponse(request, "pago_simulada.html", context)


@router.post("/pago/simulado/{referencia}")
async def decidir_simulada(
    request: Request,
    referencia: str,
    decision: str = Form(...),
):
    sesion = obtener_sesion_actual(request)
    if not sesion:
        raise HTTPException(status_code=401, detail="No estás logueado")
    pago = PagoModel.obtener_por_referencia(referencia)
    if pago is None or not _es_dueno(sesion, pago) or pago.proveedor != "simulada":
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    if decision not in ("aprobar", "rechazar"):
        raise HTTPException(status_code=400, detail="Decisión inválida")

    nuevo = ESTADO_APROBADO if decision == "aprobar" else ESTADO_RECHAZADO
    PagoModel.actualizar_estado(referencia, nuevo)
    return RedirectResponse(url=f"/pago/retorno/{referencia}", status_code=303)
