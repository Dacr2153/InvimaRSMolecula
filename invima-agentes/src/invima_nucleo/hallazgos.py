"""Consolidacion de hallazgos y guardia lexica de la salida.

Compartida por todos los agentes: la prohibicion del art. 7.1 no es de un
agente, es del sistema.

Aqui termina la auditoria y aqui NO empieza un concepto. El agente entrega el
conteo por severidad, la lista ordenada y la sugerencia de a que items conviene
que mire un especialista. No emite un estado global del expediente ni una
recomendacion de aprobacion: esa frase la escribe el evaluador y la firma.

La guardia lexica hace de esa promesa algo verificable por una prueba: recorre
el payload de salida y falla si aparece vocabulario decisorio.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from .modelos import ORDEN_SEVERIDAD, ClaseHallazgo, Hallazgo, Severidad
from .valores import Dato

#: Vocabulario que ninguna salida del agente puede contener. Sale del articulo
#: 7.1 de la Resolucion 2026025611: la IA no adopta la decision administrativa,
#: asi que tampoco usa sus verbos.
LEXICO_PROHIBIDO: tuple[str, ...] = (
    "aprobar",
    "aprobado",
    "aprobada",
    "aprobacion",
    "rechazar",
    "rechazado",
    "rechazada",
    "rechazo",
    "cumple",
    "incumple",
    "cumplimiento",
    "conforme",
    "conformidad",
    "no conforme",
    "apto",
    "idoneo",
    "puntaje",
    "calificacion",
    "score",
    "negar",
    "negado",
    "conceder",
    "otorgar",
)

_PATRON_PROHIBIDO = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in LEXICO_PROHIBIDO) + r")\b",
    re.IGNORECASE,
)


def terminos_decisorios(texto: str) -> tuple[str, ...]:
    """Devuelve el vocabulario decisorio hallado en un texto, sin duplicados."""
    hallados: list[str] = []
    for coincidencia in _PATRON_PROHIBIDO.finditer(texto):
        termino = coincidencia.group(0).lower()
        if termino not in hallados:
            hallados.append(termino)
    return tuple(hallados)


def auditar_lexico(payload: Any, ruta: str = "$") -> tuple[tuple[str, str], ...]:
    """Recorre un payload serializable y reporta (ruta, termino) por cada desvio.

    Se usa en pruebas y antes de escribir el JSON: si esta funcion devuelve algo,
    el agente estaba a punto de opinar sobre la decision, no sobre la evidencia.
    """
    desvios: list[tuple[str, str]] = []
    if isinstance(payload, str):
        for termino in terminos_decisorios(payload):
            desvios.append((ruta, termino))
    elif isinstance(payload, dict):
        for clave, valor in payload.items():
            desvios.extend(auditar_lexico(valor, f"{ruta}.{clave}"))
    elif isinstance(payload, (list, tuple)):
        for indice, valor in enumerate(payload):
            desvios.extend(auditar_lexico(valor, f"{ruta}[{indice}]"))
    return tuple(desvios)


def ordenar(hallazgos: Iterable[Hallazgo]) -> tuple[Hallazgo, ...]:
    """Severidad primero, luego parametro. Orden estable y reproducible."""
    return tuple(
        sorted(hallazgos, key=lambda h: (ORDEN_SEVERIDAD[h.severidad], h.parametro))
    )


@dataclass(frozen=True, slots=True)
class ResumenAuditoria:
    """Conteos y prioridades. Nunca un estado global del expediente."""

    total: int
    por_severidad: dict[str, int]
    por_clase: dict[str, int]
    parametros_sin_especificacion: tuple[str, ...]
    parametros_sin_resultado: tuple[str, ...]
    sugeridos_a_especialista: tuple[str, ...]
    cobertura_verificable: Dato[float]

    def a_dict(self) -> dict[str, Any]:
        return {
            "total_hallazgos": self.total,
            "por_severidad": self.por_severidad,
            "por_clase": self.por_clase,
            "parametros_sin_especificacion_declarada": list(
                self.parametros_sin_especificacion
            ),
            "parametros_sin_resultado_reportado": list(self.parametros_sin_resultado),
            "sugeridos_para_lectura_de_especialista": list(
                self.sugeridos_a_especialista
            ),
            "cobertura_verificable": self.cobertura_verificable.a_dict(),
        }


def consolidar(hallazgos: Sequence[Hallazgo]) -> ResumenAuditoria:
    """Resume la tanda de hallazgos sin pronunciarse sobre el expediente.

    `cobertura_verificable` responde a una pregunta que el spec original ni se
    hacia: de todo lo que se miro, que fraccion pudo contrastarse de verdad
    contra un limite declarado. Una auditoria con 95% de hallazgos "dentro de
    especificacion" sobre una cobertura del 30% no dice lo que parece decir.
    """
    por_severidad: dict[str, int] = {str(s): 0 for s in Severidad}
    por_clase: dict[str, int] = {str(c): 0 for c in ClaseHallazgo}
    sin_especificacion: list[str] = []
    sin_resultado: list[str] = []
    especialista: list[str] = []

    for hallazgo in hallazgos:
        por_severidad[str(hallazgo.severidad)] += 1
        por_clase[str(hallazgo.clase)] += 1
        if hallazgo.clase is ClaseHallazgo.ESPECIFICACION_NO_DECLARADA:
            sin_especificacion.append(hallazgo.parametro)
        if hallazgo.clase is ClaseHallazgo.RESULTADO_NO_SUMINISTRADO:
            sin_resultado.append(hallazgo.parametro)
        if hallazgo.exige_lectura_humana:
            especialista.append(hallazgo.parametro)

    contrastables = por_clase[str(ClaseHallazgo.DENTRO_DE_ESPECIFICACION)] + por_clase[
        str(ClaseHallazgo.FUERA_DE_ESPECIFICACION)
    ]
    total = len(hallazgos)
    fraccion = round(contrastables / total * 100, 2) if total else 0.0
    cobertura = Dato.recomendado(
        fraccion,
        razon=(
            f"{contrastables} de {total} hallazgos pudieron contrastarse contra un "
            f"limite declarado en el expediente; el resto quedo sin especificacion, "
            f"sin resultado o sin unidades comparables"
        ),
    )

    return ResumenAuditoria(
        total=total,
        por_severidad=por_severidad,
        por_clase=por_clase,
        parametros_sin_especificacion=tuple(dict.fromkeys(sin_especificacion)),
        parametros_sin_resultado=tuple(dict.fromkeys(sin_resultado)),
        sugeridos_a_especialista=tuple(dict.fromkeys(especialista)),
        cobertura_verificable=cobertura,
    )
