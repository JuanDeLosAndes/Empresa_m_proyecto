from __future__ import annotations

import hashlib
import hmac
import os
import re
from dataclasses import dataclass, field
from urllib.parse import urlencode, urlsplit

import httpx


class PagosNoConfigurados(RuntimeError):
    pass


class ProveedorNoDisponible(RuntimeError):
    pass


@dataclass(frozen=True)
class ConfiguracionWompi:
    ambiente: str
    publica: str
    privada: str = field(repr=False)
    integridad: str = field(repr=False)
    eventos: str = field(repr=False)
    base_url: str

    @classmethod
    def desde_entorno(cls):
        ambiente = os.getenv("WOMPI_AMBIENTE", "test").strip()
        if ambiente not in {"test", "prod"}:
            raise PagosNoConfigurados("WOMPI_AMBIENTE debe ser test o prod.")
        claves = [os.getenv(k, "").strip() for k in (
            "WOMPI_PUBLIC_KEY", "WOMPI_PRIVATE_KEY", "WOMPI_INTEGRITY_SECRET", "WOMPI_EVENTS_SECRET"
        )]
        prefijos = [f"pub_{ambiente}_", f"prv_{ambiente}_", f"{ambiente}_integrity_", f"{ambiente}_events_"]
        if not all(valor.startswith(prefijo) and len(valor) > len(prefijo) for valor, prefijo in zip(claves, prefijos)):
            raise PagosNoConfigurados("Configura las cuatro llaves de Wompi para el mismo ambiente.")
        base = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
        url = urlsplit(base)
        if (url.scheme != "https" or not url.netloc or url.path or url.query or url.fragment or url.username):
            raise PagosNoConfigurados("PUBLIC_BASE_URL debe contener el dominio HTTPS de la aplicación.")
        if ambiente == "prod" and (not os.getenv("MSPS_DB_PATH") or len(os.getenv("MSPS_SECRET_KEY", "")) < 32):
            raise PagosNoConfigurados("Antes de cobrar, configura MSPS_DB_PATH persistente y MSPS_SECRET_KEY fija.")
        return cls(ambiente, *claves, base)


class Wompi:
    """Checkout alojado: la aplicación no recibe números de tarjeta ni CVV."""
    def __init__(self, configuracion: ConfiguracionWompi):
        self.config = configuracion
        self.ambiente = configuracion.ambiente

    def url_checkout(self, pedido: dict) -> str:
        firma = hashlib.sha256(
            f"{pedido['referencia']}{pedido['total_centavos']}COP{pedido['vence_iso']}{self.config.integridad}".encode()
        ).hexdigest()
        parametros = {
            "public-key": self.config.publica, "currency": "COP",
            "amount-in-cents": pedido["total_centavos"], "reference": pedido["referencia"],
            "signature:integrity": firma, "expiration-time": pedido["vence_iso"],
            "redirect-url": f"{self.config.base_url}/pagos/resultado?referencia={pedido['referencia']}",
            "customer-data:email": pedido["correo"], "customer-data:full-name": pedido["nombre"],
        }
        return "https://checkout.wompi.co/p/?" + urlencode(parametros)

    def validar_evento(self, evento: dict, checksum_header: str = "") -> str:
        """Las propiedades se leen en el orden enviado por Wompi, no se fijan."""
        try:
            if evento["environment"] != self.ambiente:
                raise ValueError
            firma = evento["signature"]
            propiedades = firma["properties"]
            requeridas = {"transaction.id", "transaction.status", "transaction.amount_in_cents"}
            if (not isinstance(propiedades, list) or len(propiedades) > 32
                    or not requeridas.issubset(propiedades)):
                raise ValueError
            valores = []
            for ruta in propiedades:
                valor = evento["data"]
                for parte in ruta.split("."):
                    valor = valor[parte]
                if type(valor) not in (str, int):
                    raise ValueError
                valores.append(str(valor))
            timestamp = evento["timestamp"]
            if type(timestamp) is not int or timestamp <= 0:
                raise ValueError
            calculado = hashlib.sha256(("".join(valores) + str(timestamp) + self.config.eventos).encode()).hexdigest()
            recibido = checksum_header or firma["checksum"]
            if not isinstance(recibido, str) or not hmac.compare_digest(calculado, recibido.lower()):
                raise ValueError
            identificador = evento["data"]["transaction"]["id"]
            if not isinstance(identificador, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,150}", identificador):
                raise ValueError
            return identificador
        except (KeyError, TypeError, AttributeError, ValueError):
            raise ValueError("Firma o ambiente del evento inválidos.") from None

    def consultar(self, identificador: str) -> dict:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,150}", identificador):
            raise ValueError("Identificador de transacción inválido.")
        base = "https://production.wompi.co/v1" if self.ambiente == "prod" else "https://sandbox.wompi.co/v1"
        try:
            with httpx.Client(timeout=5, follow_redirects=False) as cliente:
                respuesta = cliente.get(f"{base}/transactions/{identificador}", headers={
                    "Authorization": f"Bearer {self.config.privada}", "Accept": "application/json"
                })
                respuesta.raise_for_status()
                datos = respuesta.json()["data"]
                if not isinstance(datos, dict) or datos.get("id") != identificador:
                    raise ValueError
                return datos
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise ProveedorNoDisponible("No se pudo verificar la transacción con Wompi. Intenta más tarde.") from None