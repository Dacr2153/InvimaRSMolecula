"""Puertos del tarifario oficial y de la base transaccional local.

Ambos son locales por diseno: la validacion del pago no debe requerir salida a
internet ni exponer datos del tramite a terceros.
"""

from __future__ import annotations

from typing import Protocol

from ..domain.modelos import Tarifa, TransaccionBancaria


class TarifarioPort(Protocol):
    def buscar(self, codigo: str) -> Tarifa | None: ...


class TransaccionesPort(Protocol):
    def buscar(self, comprobante: str) -> TransaccionBancaria | None: ...
