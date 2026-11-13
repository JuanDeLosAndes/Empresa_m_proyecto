# ======================================================================
# QUÉ HACE
#   Adaptador de Wompi (pasarela colombiana). Usa su Web Checkout: redirige al
#   cliente a checkout.wompi.co con una firma de integridad, y al volver consulta
#   la transacción en la API de Wompi para confirmar el estado real.
# HASTA DÓNDE LLEGA
#   Construye la URL firmada y consulta el estado. No guarda nada en la base
#   (eso lo hace el controlador).
# ======================================================================
from __future__ import annotations

import hashlib
from typing import Optional
from urllib.parse import urlencode

import httpx

from app.pagos.pasarela import (
    ESTADO_APROBADO,
    ESTADO_ERROR,
    ESTADO_PENDIENTE,
    ESTADO_RECHAZADO,
    InicioPago,
    PasarelaPago,
    ResultadoPago,
    SolicitudPago,
)

CHECKOUT_URL = "https://checkout.wompi.co/p/"
API_SANDBOX = "https://api-sandbox.co.uat.wompi.dev/v1"
API_PRODUCCION = "https://production.wompi.co/v1"

_ESTADOS_WOMPI = {
    "APPROVED": ESTADO_APROBADO,
    "DECLINED": ESTADO_RECHAZADO,
    "VOIDED": ESTADO_RECHAZADO,
    "ERROR": ESTADO_ERROR,
    "PENDING": ESTADO_PENDIENTE,
}


class PasarelaWompi(PasarelaPago):
    nombre = "wompi"

    def __init__(self, llave_publica: str, secreto_integridad: str, api_url: str) -> None:
        self._llave_publica = llave_publica
        self._secreto = secreto_integridad
        self._api_url = api_url.rstrip("/")

    def firma_integridad(self, referencia: str, centavos: int, moneda: str = "COP") -> str:
        """Firma exigida por Wompi: SHA256(referencia + centavos + moneda + secreto)."""
        base = f"{referencia}{centavos}{moneda}{self._secreto}"
        return hashlib.sha256(base.encode("utf-8")).hexdigest()

    def iniciar(self, solicitud: SolicitudPago) -> InicioPago:
        centavos = solicitud.monto_pesos * 100
        parametros = {
            "public-key": self._llave_publica,
            "currency": "COP",
            "amount-in-cents": str(centavos),
            "reference": solicitud.referencia,
            "signature:integrity": self.firma_integridad(solicitud.referencia, centavos),
            "redirect-url": solicitud.url_retorno,
        }
        return InicioPago(url_pago=f"{CHECKOUT_URL}?{urlencode(parametros)}")

    def verificar(self, referencia: str, transaccion_id: Optional[str]) -> ResultadoPago:
        if not transaccion_id:
            # Wompi no devolvió el id de transacción: aún no hay resultado que confirmar.
            return ResultadoPago(estado=ESTADO_PENDIENTE, referencia=referencia)
        try:
            respuesta = httpx.get(f"{self._api_url}/transactions/{transaccion_id}", timeout=10)
            respuesta.raise_for_status()
            datos = respuesta.json()["data"]
        except (httpx.HTTPError, KeyError, ValueError):
            return ResultadoPago(estado=ESTADO_ERROR, referencia=referencia, transaccion_id=transaccion_id)

        # La referencia debe coincidir: evita usar la transacción de otro pedido.
        if datos.get("reference") != referencia:
            return ResultadoPago(estado=ESTADO_ERROR, referencia=referencia, transaccion_id=transaccion_id)

        return ResultadoPago(
            estado=_ESTADOS_WOMPI.get(datos.get("status"), ESTADO_ERROR),
            referencia=referencia,
            monto_pesos=int(datos.get("amount_in_cents", 0)) // 100,
            transaccion_id=transaccion_id,
        )
