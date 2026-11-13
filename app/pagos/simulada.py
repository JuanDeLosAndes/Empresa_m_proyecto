# ======================================================================
# QUÉ HACE
#   Pasarela de PRUEBA: no cobra nada. Muestra una página propia donde se decide
#   aprobar o rechazar el pago. Sirve para desarrollar y probar sin cuentas.
# HASTA DÓNDE LLEGA
#   Solo lee el estado que guardó el simulador en la tabla pagos. Está prohibida
#   en producción (ver factories.crear_pasarela_pago).
# ======================================================================
from __future__ import annotations

from typing import Optional

from app.models.pago import PagoModel
from app.pagos.pasarela import (
    InicioPago,
    PasarelaPago,
    ResultadoPago,
    SolicitudPago,
)


class PasarelaSimulada(PasarelaPago):
    nombre = "simulada"

    def iniciar(self, solicitud: SolicitudPago) -> InicioPago:
        return InicioPago(url_pago=f"/pago/simulado/{solicitud.referencia}")

    def verificar(self, referencia: str, transaccion_id: Optional[str]) -> ResultadoPago:
        pago = PagoModel.obtener_por_referencia(referencia)
        if pago is None:
            return ResultadoPago(estado="error", referencia=referencia)
        return ResultadoPago(
            estado=pago.estado,
            referencia=referencia,
            monto_pesos=pago.monto,
            transaccion_id=f"SIM-{referencia}",
        )
