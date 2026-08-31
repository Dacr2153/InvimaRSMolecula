"""Tarifario oficial y base transaccional desde CSV local.

Locales por diseno: validar el pago no debe exigir salida a internet ni exponer
datos del tramite a terceros.
"""

from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

from ...domain.modelos import Tarifa, TransaccionBancaria
from ...domain.valores import Dinero


class TarifarioCSV:
    def __init__(self, ruta: Path) -> None:
        self._tarifas: dict[str, Tarifa] = {}
        with ruta.open(encoding="utf-8", newline="") as archivo:
            for fila in csv.DictReader(archivo):
                codigo = fila["codigo"].strip()
                self._tarifas[codigo] = Tarifa(
                    codigo=codigo,
                    concepto=fila["concepto"].strip(),
                    valor_esperado=Dinero(Decimal(fila["valor"].strip())),
                )

    def buscar(self, codigo: str) -> Tarifa | None:
        return self._tarifas.get(codigo.strip())


class TransaccionesCSV:
    def __init__(self, ruta: Path) -> None:
        self._transacciones: dict[str, TransaccionBancaria] = {}
        with ruta.open(encoding="utf-8", newline="") as archivo:
            for fila in csv.DictReader(archivo):
                comprobante = fila["comprobante"].strip()
                self._transacciones[comprobante] = TransaccionBancaria(
                    comprobante_numero=comprobante,
                    valor_recibido=Dinero(Decimal(fila["valor"].strip())),
                    fecha=date.fromisoformat(fila["fecha"].strip()),
                )

    def buscar(self, comprobante: str) -> TransaccionBancaria | None:
        return self._transacciones.get(comprobante.strip())
