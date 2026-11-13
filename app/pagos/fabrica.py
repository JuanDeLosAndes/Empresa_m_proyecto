# ======================================================================
# QUÉ HACE
#   Factory Method: decide QUÉ pasarela usa la app según la variable MSPS_PASARELA.
#   Los controladores solo piden "la pasarela", sin saber cuál es.
# ======================================================================
from __future__ import annotations

import os

from app.pagos.pasarela import PasarelaPago
from app.pagos.simulada import PasarelaSimulada
from app.pagos.wompi import API_PRODUCCION, API_SANDBOX, PasarelaWompi


def crear_pasarela_pago() -> PasarelaPago:
    proveedor = os.environ.get("MSPS_PASARELA", "simulada").strip().lower()
    en_produccion = os.environ.get("MSPS_ENTORNO", "desarrollo").lower() == "produccion"

    if proveedor == "simulada":
        if en_produccion:
            raise RuntimeError("La pasarela simulada no puede usarse en producción.")
        return PasarelaSimulada()

    if proveedor == "wompi":
        llave = os.environ.get("WOMPI_LLAVE_PUBLICA", "")
        secreto = os.environ.get("WOMPI_SECRETO_INTEGRIDAD", "")
        if not llave or not secreto:
            raise RuntimeError("Faltan WOMPI_LLAVE_PUBLICA o WOMPI_SECRETO_INTEGRIDAD.")
        api = os.environ.get("WOMPI_API_URL") or (API_PRODUCCION if en_produccion else API_SANDBOX)
        return PasarelaWompi(llave, secreto, api)

    raise ValueError(f"Pasarela de pago desconocida: {proveedor}")
