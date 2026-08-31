"""Estadistica descriptiva sobre series de resultados de liberacion.

Aritmetica en Decimal de punta a punta: los resultados de liberacion se comparan
contra limites con dos y tres decimales, y un error de redondeo binario puede
mover un lote de un lado a otro de la especificacion.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Sequence

from .errores import SerieInsuficienteError

DOS_DECIMALES = Decimal("0.01")
CUATRO_DECIMALES = Decimal("0.0001")


@dataclass(frozen=True, slots=True)
class ResumenEstadistico:
    """Promedio, dispersion y coeficiente de variacion de una serie."""

    n: int
    promedio: Decimal
    desviacion_estandar: Decimal
    coeficiente_variacion: Decimal | None
    minimo: Decimal
    maximo: Decimal

    def a_dict(self) -> dict[str, Any]:
        return {
            "n": self.n,
            "promedio": float(self.promedio.quantize(CUATRO_DECIMALES)),
            "desviacion_estandar": float(
                self.desviacion_estandar.quantize(CUATRO_DECIMALES)
            ),
            "coeficiente_variacion_porcentaje": (
                float(self.coeficiente_variacion.quantize(DOS_DECIMALES))
                if self.coeficiente_variacion is not None
                else None
            ),
            "minimo": float(self.minimo),
            "maximo": float(self.maximo),
        }


def resumir(valores: Sequence[Decimal]) -> ResumenEstadistico:
    """Calcula el resumen de una serie con desviacion estandar muestral (n-1).

    Muestral y no poblacional porque los lotes auditados son una muestra del
    proceso, no el universo de lo que la planta va a fabricar.
    """
    n = len(valores)
    if n < 2:
        raise SerieInsuficienteError(
            f"La dispersion exige al menos dos observaciones; se recibieron {n}"
        )
    promedio = sum(valores, Decimal(0)) / Decimal(n)
    suma_cuadrados = sum(((v - promedio) ** 2 for v in valores), Decimal(0))
    varianza = suma_cuadrados / Decimal(n - 1)
    desviacion = varianza.sqrt()
    cv = None if promedio == 0 else desviacion / promedio * Decimal(100)
    return ResumenEstadistico(
        n=n,
        promedio=promedio,
        desviacion_estandar=desviacion,
        coeficiente_variacion=cv,
        minimo=min(valores),
        maximo=max(valores),
    )
