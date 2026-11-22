from __future__ import annotations

import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Protocol

from app.models.carrito import ResumenCarrito


def centavos(valor) -> int:
    numero = Decimal(str(valor))
    if not numero.is_finite() or numero < 0:
        raise ValueError("El importe no es válido.")
    return int((numero * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def acepta_actualizacion(pedido: dict, transaccion: dict) -> bool:
    if pedido["transaccion_id"] and pedido["transaccion_id"] != transaccion["id"]:
        raise ValueError("La referencia ya está asociada a otra transacción.")
    anterior, nuevo = pedido["estado"], transaccion["status"]
    if anterior == "VOIDED":
        return False
    if anterior == "APPROVED":
        return nuevo == "VOIDED"
    return not (anterior in {"DECLINED", "ERROR"} and nuevo == "PENDING")


class Pasarela(Protocol):
    ambiente: str
    def url_checkout(self, pedido: dict) -> str: ...
    def validar_evento(self, evento: dict, checksum_header: str = "") -> str: ...
    def consultar(self, identificador: str) -> dict: ...


class Pedidos(Protocol):
    def crear_o_reutilizar(self, pedido: dict) -> dict: ...
    def obtener(self, referencia: str) -> dict | None: ...
    def actualizar(self, referencia: str, datos: dict, ahora: int) -> dict: ...
    def listar(self, tipo: str, identificador: int, administrador=False) -> list[dict]: ...


class ConsultaPagosModel:
    def __init__(self, pedidos: Pedidos):
        self._pedidos = pedidos

    def historial(self, sesion: dict) -> list[dict]:
        return self._pedidos.listar(sesion["tipo"], sesion["id"], sesion["tipo"] == "administrador")

    @staticmethod
    def _propio(pedido, sesion):
        return (pedido["propietario_tipo"], pedido["propietario_id"]) == (sesion["tipo"], sesion["id"])

    def obtener_visible(self, referencia: str, sesion: dict) -> dict:
        pedido = self._pedidos.obtener(referencia)
        if pedido is None or (sesion["tipo"] != "administrador" and not self._propio(pedido, sesion)):
            raise LookupError("Pedido no encontrado.")
        return {**pedido, "lineas": json.loads(pedido["lineas_json"])}

    def lineas_pagadas(self, referencia: str, sesion: dict):
        pedido = self.obtener_visible(referencia, sesion)
        if pedido["estado"] != "APPROVED" or not self._propio(pedido, sesion):
            raise ValueError("El pago debe estar aprobado y pertenecer a tu cuenta.")
        return pedido["lineas"]


class PagosModel:
    def __init__(self, pedidos: Pedidos, pasarela: Pasarela):
        self._pedidos = pedidos
        self._pasarela = pasarela

    @property
    def ambiente(self):
        return self._pasarela.ambiente

    def preparar(self, sesion: dict, correo: str, resumen: ResumenCarrito) -> dict:
        if not resumen.lineas:
            raise ValueError("El carrito está vacío.")
        lineas = [{
            "id_maquinaria": l.maquina.id_maquinaria, "placa": l.maquina.placa,
            "nombre": f"{l.maquina.marca} {l.maquina.modelo or ''}".strip(),
            "horas": l.horas, "precio_hora_centavos": centavos(l.maquina.costo_por_hora),
            "total_centavos": centavos(l.total),
        } for l in resumen.lineas]
        lineas_json = json.dumps(lineas, sort_keys=True, ensure_ascii=False)
        subtotal = centavos(resumen.subtotal)
        iva = centavos(resumen.iva)
        total = centavos(resumen.total)
        if total <= 0 or total > 9_000_000_000_000_000:
            raise ValueError("El total del pedido no es válido.")
        ahora = int(time.time())
        vence = ahora + 1800
        pedido = self._pedidos.crear_o_reutilizar({
            "referencia": "MSPS-" + uuid.uuid4().hex,
            "propietario_tipo": sesion["tipo"], "propietario_id": sesion["id"],
            "nombre": sesion["nombre"], "correo": correo,
            "ambiente": self._pasarela.ambiente,
            "huella": hashlib.sha256(f"{lineas_json}|{iva}|{correo}".encode()).hexdigest(),
            "lineas_json": lineas_json, "subtotal_centavos": subtotal, "iva_centavos": iva,
            "total_centavos": total, "creada": ahora, "vence": vence,
            "vence_iso": datetime.fromtimestamp(vence, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "actualizada": ahora,
        })
        return pedido

    def url_checkout(self, pedido: dict) -> str:
        return self._pasarela.url_checkout(pedido)

    def recibir_evento(self, evento: dict, checksum: str = "") -> dict | None:
        identificador = self._pasarela.validar_evento(evento, checksum)
        if evento.get("event") != "transaction.updated":
            return None
        return self.conciliar(identificador)

    def conciliar(self, identificador: str) -> dict | None:
        # El checksum no siempre cubre referencia/moneda. Se contrastan contra
        # el API autenticado, nunca contra datos enviados por el navegador.
        datos = self._pasarela.consultar(identificador)
        referencia = datos.get("reference", "")
        if not isinstance(referencia, str) or not referencia or len(referencia) > 200:
            raise ValueError("Referencia de pago inválida.")
        pedido = self._pedidos.obtener(referencia)
        if pedido is None:
            return None  # Puede ser otro pago del mismo comercio, ajeno a esta app.
        importe = datos.get("amount_in_cents")
        if (pedido["ambiente"] != self._pasarela.ambiente or datos.get("currency") != "COP"
                or type(importe) is not int or importe != pedido["total_centavos"]
                or datos.get("status") not in {"PENDING", "APPROVED", "DECLINED", "ERROR", "VOIDED"}):
            raise ValueError("La transacción no coincide con el importe, moneda o ambiente del pedido.")
        return self._pedidos.actualizar(referencia, datos, int(time.time()))