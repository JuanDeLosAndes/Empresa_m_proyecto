from __future__ import annotations

import hmac
import secrets

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.builders import PageContextBuilder
from app.controllers.dependencias import exigir_sesion, exigir_admin
from app.current_user import SesionActual, obtener_sesion_actual
from app.factories import crear_carrito, crear_consulta_pagos, crear_pagos
from app.models.registro_verificado import validar_correo
from app.pagos.wompi import PagosNoConfigurados, ProveedorNoDisponible
from app.templating import templates

router = APIRouter()


def _csrf(request):
    if "pago_csrf" not in request.session:
        request.session["pago_csrf"] = secrets.token_urlsafe(32)
    return request.session["pago_csrf"]


def _validar_csrf(request, token):
    esperado = request.session.get("pago_csrf", "")
    if not esperado or not hmac.compare_digest(esperado, token):
        raise HTTPException(403, "La sesión del formulario venció. Abre la página nuevamente.")


def _contexto(request, sesion, titulo):
    return PageContextBuilder().with_title(titulo).with_sesion(sesion).build()


def _pedido_autorizado(referencia, sesion):
    try:
        return crear_consulta_pagos().obtener_visible(referencia, sesion)
    except LookupError as error:
        raise HTTPException(404, str(error)) from None


def _pagina_checkout(request, sesion, error="", status=200):
    contexto = _contexto(request, sesion, "Confirmar pago · MSPS")
    resumen = crear_carrito(request).resumen()
    correo = sesion.get("correo") or ""
    habilitado, ambiente = False, "test"
    try:
        ambiente = crear_pagos().ambiente
        habilitado = True
    except PagosNoConfigurados:
        pass
    contexto.update(resumen=resumen, csrf=_csrf(request), correo=correo,
                    error=error, pagos_habilitados=habilitado, ambiente=ambiente)
    return templates.TemplateResponse(request, "checkout.html", contexto, status_code=status,
                                      headers={"Cache-Control": "no-store"})


@router.get("/checkout")
def checkout(request: Request):
    sesion = obtener_sesion_actual(request)
    if not sesion:
        return RedirectResponse("/?acceso=login", status_code=303)
    return _pagina_checkout(request, sesion)


@router.post("/pagos/checkout")
def iniciar_pago(request: Request, csrf: str = Form(...), correo: str = Form(...),
                 sesion: SesionActual = Depends(exigir_sesion)):
    _validar_csrf(request, csrf)
    try:
        correo = validar_correo(correo)
        carrito = crear_carrito(request)
        resumen = carrito.resumen_para_pago()
        modelo = crear_pagos()
        pedido = modelo.preparar(sesion, correo, resumen)
    except ValueError as error:
        return _pagina_checkout(request, sesion, str(error), 400)
    except PagosNoConfigurados:
        return _pagina_checkout(request, sesion, "Los pagos en línea aún no están habilitados. Contacta al equipo.", 503)
    request.session["ultimo_pedido"] = pedido["referencia"]
    return RedirectResponse(modelo.url_checkout(pedido), status_code=303)


@router.post("/api/pagos/wompi/eventos/{ambiente}")
def evento_wompi(ambiente: str, evento: dict, request: Request):
    try:
        modelo = crear_pagos()
        if ambiente != modelo.ambiente:
            raise HTTPException(400, "Ambiente de pago incorrecto.")
        if evento.get("event") != "transaction.updated":
            return {"recibido": True}
        modelo.recibir_evento(evento, request.headers.get("x-event-checksum", ""))
    except PagosNoConfigurados:
        raise HTTPException(503, "Falta configurar la pasarela.") from None
    except ProveedorNoDisponible:
        # Wompi reintentará; no aceptar como confirmado un pago sin verificar.
        raise HTTPException(503, "Verificación temporalmente no disponible.") from None
    except ValueError as error:
        raise HTTPException(400, str(error)) from None
    return {"recibido": True}


@router.get("/pagos")
def historial(request: Request):
    sesion = obtener_sesion_actual(request)
    if not sesion:
        return RedirectResponse("/?acceso=login", status_code=303)
    pedidos = crear_consulta_pagos().historial(sesion)
    contexto = _contexto(request, sesion, "Mis pagos · MSPS")
    contexto.update(pedidos=pedidos, csrf=_csrf(request), aviso=request.query_params.get("aviso", ""))
    return templates.TemplateResponse(request, "pagos.html", contexto, headers={"Cache-Control": "no-store"})


@router.get("/pagos/resultado")
def resultado(request: Request, referencia: str = ""):
    sesion = obtener_sesion_actual(request)
    if not sesion:
        return RedirectResponse("/?acceso=login", status_code=303)
    referencia = referencia or request.session.get("ultimo_pedido", "")
    pedido = _pedido_autorizado(referencia, sesion)
    contexto = _contexto(request, sesion, "Estado del pago · MSPS")
    contexto.update(pedido=pedido, lineas=pedido["lineas"], csrf=_csrf(request))
    # El parámetro id/status de la redirección nunca confirma un pago.
    return templates.TemplateResponse(request, "pago_resultado.html", contexto,
                                      headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})


@router.get("/api/pagos/{referencia}")
def estado_pago(referencia: str, sesion: SesionActual = Depends(exigir_sesion)):
    pedido = _pedido_autorizado(referencia, sesion)
    return JSONResponse({"estado": pedido["estado"], "referencia": referencia,
                         "total_centavos": pedido["total_centavos"]}, headers={"Cache-Control": "no-store"})


@router.post("/pagos/{referencia}/limpiar-carrito")
def retirar_pagados(referencia: str, request: Request, csrf: str = Form(...),
                    sesion: SesionActual = Depends(exigir_sesion)):
    _validar_csrf(request, csrf)
    try:
        lineas = crear_consulta_pagos().lineas_pagadas(referencia, sesion)
    except LookupError as error:
        raise HTTPException(404, str(error)) from None
    except ValueError as error:
        raise HTTPException(409, str(error)) from None
    crear_carrito(request).retirar_pagados(lineas)
    return RedirectResponse("/carrito", status_code=303)


@router.post("/admin/pagos/conciliar")
def conciliar_pago(request: Request, transaccion_id: str = Form(...), csrf: str = Form(...),
                   _: SesionActual = Depends(exigir_admin)):
    """Recuperación cuando un webhook no llegó. Consulta privada autenticada."""
    _validar_csrf(request, csrf)
    try:
        pedido = crear_pagos().conciliar(transaccion_id.strip())
    except PagosNoConfigurados:
        return RedirectResponse("/pagos?aviso=configuracion", status_code=303)
    except ProveedorNoDisponible:
        return RedirectResponse("/pagos?aviso=proveedor", status_code=303)
    except ValueError:
        return RedirectResponse("/pagos?aviso=datos", status_code=303)
    if pedido is None:
        return RedirectResponse("/pagos?aviso=desconocido", status_code=303)
    return RedirectResponse("/pagos/resultado?referencia=" + pedido["referencia"], status_code=303)
