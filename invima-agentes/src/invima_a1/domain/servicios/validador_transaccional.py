"""Validacion transaccional del pago.

Cruza tres cosas que deben coincidir exactamente: el comprobante declarado en el
formulario contra el registro bancario, el codigo de tarifa contra el tarifario
oficial, y el valor pagado contra el valor esperado de esa tarifa.

Se ejecuta antes de cualquier busqueda o llamada al modelo: un pago inconsistente
corta el flujo y ahorra tokens.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from ..modelos import Pago, Tarifa, TransaccionBancaria


class CampoInconsistente(StrEnum):
    COMPROBANTE = "COMPROBANTE"
    CODIGO_TARIFA = "CODIGO_TARIFA"
    VALOR = "VALOR"
    DATO_FALTANTE = "DATO_FALTANTE"


@dataclass(frozen=True, slots=True)
class Inconsistencia:
    """Discrepancia concreta. Dice que campo, que se esperaba y que llego."""

    campo: CampoInconsistente
    esperado: str
    encontrado: str
    mensaje: str


@dataclass(frozen=True, slots=True)
class ResultadoValidacionPago:
    conforme: bool
    inconsistencias: tuple[Inconsistencia, ...] = ()

    @property
    def resumen(self) -> str:
        if self.conforme:
            return "Pago verificado: comprobante, tarifa y valor coinciden"
        return "; ".join(i.mensaje for i in self.inconsistencias)


def validar_pago(
    pago: Pago,
    tarifa: Tarifa | None,
    transaccion: TransaccionBancaria | None,
    tolerancia: Decimal = Decimal("0"),
) -> ResultadoValidacionPago:
    """Verifica la correspondencia exacta entre lo declarado y lo registrado.

    `tarifa` es None cuando el codigo declarado no existe en el tarifario.
    `transaccion` es None cuando el comprobante no aparece en la base transaccional.
    """
    fallas: list[Inconsistencia] = []

    if not pago.comprobante_numero.presente:
        fallas.append(
            Inconsistencia(
                campo=CampoInconsistente.DATO_FALTANTE,
                esperado="Numero de comprobante en el formulario",
                encontrado="No suministrado",
                mensaje="El formulario no reporta numero de comprobante",
            )
        )
    if not pago.codigo_tarifa.presente:
        fallas.append(
            Inconsistencia(
                campo=CampoInconsistente.DATO_FALTANTE,
                esperado="Codigo de tarifa en el formulario",
                encontrado="No suministrado",
                mensaje="El formulario no reporta codigo de tarifa",
            )
        )
    if not pago.valor_pagado.presente:
        fallas.append(
            Inconsistencia(
                campo=CampoInconsistente.DATO_FALTANTE,
                esperado="Valor pagado en el formulario",
                encontrado="No suministrado",
                mensaje="El formulario no reporta valor pagado",
            )
        )

    if fallas:
        return ResultadoValidacionPago(conforme=False, inconsistencias=tuple(fallas))

    comprobante = pago.comprobante_numero.exigir()
    codigo = pago.codigo_tarifa.exigir()
    valor = pago.valor_pagado.exigir()

    if transaccion is None:
        fallas.append(
            Inconsistencia(
                campo=CampoInconsistente.COMPROBANTE,
                esperado=f"Comprobante {comprobante} en la base transaccional",
                encontrado="No encontrado",
                mensaje=(
                    f"El comprobante {comprobante} declarado en el formulario no "
                    f"aparece en la base transaccional"
                ),
            )
        )
    elif transaccion.comprobante_numero != comprobante:
        fallas.append(
            Inconsistencia(
                campo=CampoInconsistente.COMPROBANTE,
                esperado=comprobante,
                encontrado=transaccion.comprobante_numero,
                mensaje="El comprobante declarado no coincide con el registrado",
            )
        )

    if tarifa is None:
        fallas.append(
            Inconsistencia(
                campo=CampoInconsistente.CODIGO_TARIFA,
                esperado=f"Codigo {codigo} en el tarifario vigente",
                encontrado="No existe",
                mensaje=f"El codigo de tarifa {codigo} no existe en el tarifario vigente",
            )
        )
    else:
        diferencia = abs(valor.monto - tarifa.valor_esperado.monto)
        if diferencia > tolerancia:
            fallas.append(
                Inconsistencia(
                    campo=CampoInconsistente.VALOR,
                    esperado=str(tarifa.valor_esperado),
                    encontrado=str(valor),
                    mensaje=(
                        f"El valor pagado {valor} no corresponde a la tarifa {codigo} "
                        f"({tarifa.concepto}), cuyo valor es {tarifa.valor_esperado}"
                    ),
                )
            )
        if transaccion is not None and transaccion.valor_recibido.monto != valor.monto:
            fallas.append(
                Inconsistencia(
                    campo=CampoInconsistente.VALOR,
                    esperado=str(valor),
                    encontrado=str(transaccion.valor_recibido),
                    mensaje=(
                        "El valor declarado en el formulario no coincide con el valor "
                        "efectivamente recibido segun la base transaccional"
                    ),
                )
            )

    return ResultadoValidacionPago(
        conforme=not fallas, inconsistencias=tuple(fallas)
    )
