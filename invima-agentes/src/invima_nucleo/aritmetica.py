"""Recalculo de los valores derivados que el expediente declara.

Un dossier trae dos clases de numero: los que se midieron y los que se
calcularon a partir de otros. Los segundos son verificables sin salir del
documento -- una tasa por 1000 pacientes-ano, un porcentaje, una diferencia
entre brazos, un margen de seguridad -- y por eso son el sitio donde un error
de transcripcion o de denominador se puede atrapar de forma determinista.

El agente no corrige el numero declarado ni lo reemplaza en la salida: reporta
los dos, la formula con la que llego al suyo, y el factor entre ambos. Quien
decide cual vale es el evaluador.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, DivisionByZero, InvalidOperation
from typing import Any, Sequence

from .modelos import ClaseHallazgo, Hallazgo, Severidad
from .valores import Dato

#: Holgura relativa con que se acepta que un valor declarado reproduzca el
#: recalculado. Criterio operativo del agente: absorbe el redondeo con que el
#: solicitante reporta, no es una especificacion normativa.
TOLERANCIA_RELATIVA = Decimal("0.01")

_FACTORES_NOTABLES = (Decimal(10), Decimal(100), Decimal(1000))


def _mostrar(valor: Decimal) -> str:
    """Recorta la cola decimal para el texto; la comparacion usa el valor pleno."""
    recortado = valor.quantize(Decimal("0.0001")).normalize()
    return f"{recortado:f}"


def _texto_componentes(componentes: Sequence[tuple[str, Decimal]]) -> str:
    return ", ".join(f"{nombre} = {valor}" for nombre, valor in componentes)


def _factor_notable(factor: Decimal) -> str:
    """Nombra el factor cuando el desvio huele a error de escala o denominador."""
    for notable in _FACTORES_NOTABLES:
        for candidato, sentido in ((notable, "mayor"), (Decimal(1) / notable, "menor")):
            if candidato == 0:
                continue
            desvio = abs(factor - candidato) / candidato
            if desvio <= Decimal("0.02"):
                escala = notable if sentido == "mayor" else notable
                return (
                    f" El recalculado es aproximadamente {escala} veces "
                    f"{'mayor' if sentido == 'mayor' else 'menor'} que el declarado, "
                    f"lo que suele indicar un cambio de escala o de denominador."
                )
    return ""


@dataclass(frozen=True, slots=True)
class Derivado:
    """Un valor calculado a partir de otros valores del mismo expediente."""

    nombre: str
    formula: str
    componentes: tuple[tuple[str, Decimal], ...]
    valor: Decimal
    unidad: str = ""

    def a_dict(self) -> dict[str, Any]:
        return {
            "nombre": self.nombre,
            "formula": self.formula,
            "componentes": {nombre: float(valor) for nombre, valor in self.componentes},
            "valor_recalculado": float(self.valor),
            "unidad": self.unidad or None,
        }

    def como_dato(self) -> Dato[Decimal]:
        return Dato.recomendado(
            self.valor,
            razon=f"recalculado por el agente: {self.formula} con {_texto_componentes(self.componentes)}",
        )


def derivar(
    nombre: str,
    formula: str,
    componentes: Sequence[tuple[str, Decimal]],
    operacion,
    unidad: str = "",
) -> Derivado | None:
    """Aplica `operacion` a los componentes. Devuelve None si no es calculable."""
    try:
        valor = operacion(*[valor for _, valor in componentes])
    except (ZeroDivisionError, DivisionByZero, InvalidOperation, TypeError):
        return None
    if valor is None:
        return None
    return Derivado(
        nombre=nombre,
        formula=formula,
        componentes=tuple(componentes),
        valor=valor,
        unidad=unidad,
    )


def contrastar_derivado(
    derivado: Derivado | None,
    declarado: Dato[Decimal] | None,
    severidad_si_discrepa: Severidad = Severidad.MEDIA,
    tolerancia_relativa: Decimal = TOLERANCIA_RELATIVA,
    etiquetas: tuple[str, ...] = (),
) -> Hallazgo | None:
    """Compara el valor declarado con el que sale de sus propios componentes."""
    if derivado is None:
        return None
    unidad = f" {derivado.unidad}" if derivado.unidad else ""
    componentes = _texto_componentes(derivado.componentes)

    if declarado is None or not declarado.presente:
        return Hallazgo(
            parametro=derivado.nombre,
            clase=ClaseHallazgo.RESULTADO_NO_SUMINISTRADO,
            severidad=Severidad.BAJA,
            observacion=(
                f"El expediente no declara '{derivado.nombre}'. A partir de sus "
                f"propios componentes ({componentes}) el agente lo calcula en "
                f"{_mostrar(derivado.valor)}{unidad} mediante {derivado.formula}. El valor "
                f"calculado no reemplaza al del expediente: se ofrece para lectura."
            ),
            etiquetas=etiquetas + ("aritmetica",),
        )

    valor_declarado = declarado.exigir()
    if derivado.valor == 0:
        coincide = valor_declarado == 0
        factor = None
    else:
        diferencia = abs(valor_declarado - derivado.valor) / abs(derivado.valor)
        coincide = diferencia <= tolerancia_relativa
        factor = (
            derivado.valor / valor_declarado if valor_declarado != 0 else None
        )

    if coincide:
        return Hallazgo(
            parametro=derivado.nombre,
            clase=ClaseHallazgo.DENTRO_DE_ESPECIFICACION,
            severidad=Severidad.INFORMATIVA,
            observacion=(
                f"'{derivado.nombre}': el valor declarado {valor_declarado}{unidad} se "
                f"reproduce a partir de sus componentes ({componentes}) mediante "
                f"{derivado.formula}."
            ),
            etiquetas=etiquetas + ("aritmetica",),
        )

    detalle_factor = ""
    if factor is not None:
        detalle_factor = (
            f" Factor recalculado/declarado: {factor.quantize(Decimal('0.01'))}."
            + _factor_notable(factor)
        )
    return Hallazgo(
        parametro=derivado.nombre,
        clase=ClaseHallazgo.DISCREPANCIA_ARITMETICA,
        severidad=severidad_si_discrepa,
        observacion=(
            f"'{derivado.nombre}': el expediente declara {valor_declarado}{unidad}, "
            f"pero a partir de sus propios componentes ({componentes}) el valor es "
            f"{_mostrar(derivado.valor)}{unidad} mediante {derivado.formula}.{detalle_factor} "
            f"El agente no corrige el dato declarado; senala que los dos numeros del "
            f"expediente no concuerdan entre si."
        ),
        etiquetas=etiquetas + ("aritmetica",),
    )
