# ======================================================================
# QUÉ HACE
#   Define el contrato que cumple CUALQUIER pasarela de pago (interfaz abstracta)
#   y los datos que viajan entre la aplicación y el proveedor.
# HASTA DÓNDE LLEGA (y qué NO hace)
#   No conoce HTTP, ni la base de datos, ni las rutas. Cada proveedor concreto
#   (simulada.py, wompi.py) implementa esta interfaz.
# ======================================================================
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

ESTADO_PENDIENTE = "pendiente"
ESTADO_APROBADO = "aprobado"
ESTADO_RECHAZADO = "rechazado"
ESTADO_ERROR = "error"


@dataclass(frozen=True)
class SolicitudPago:
    referencia: str        # identificador único del pedido en nuestra app
    monto_pesos: int       # total en pesos COP, calculado en el servidor
    url_retorno: str       # a dónde vuelve el cliente tras pagar


@dataclass(frozen=True)
class InicioPago:
    url_pago: str          # a dónde se redirige al cliente para pagar


@dataclass(frozen=True)
class ResultadoPago:
    estado: str                        # pendiente | aprobado | rechazado | error
    referencia: Optional[str] = None
    monto_pesos: Optional[int] = None  # monto que la pasarela realmente cobró
    transaccion_id: Optional[str] = None


class PasarelaPago(ABC):
    nombre: str

    @abstractmethod
    def iniciar(self, solicitud: SolicitudPago) -> InicioPago:
        """Prepara el cobro y devuelve la URL donde el cliente paga."""

    @abstractmethod
    def verificar(self, referencia: str, transaccion_id: Optional[str]) -> ResultadoPago:
        """Consulta a la pasarela el estado REAL del pago. Nunca confiar en el navegador."""
