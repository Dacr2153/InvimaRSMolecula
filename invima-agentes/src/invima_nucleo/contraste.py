"""Contraste generico de una tanda de parametros.

Los auditores especificos (sustancia activa, inactivacion viral, envase-cierre)
se reducen casi por completo a "esta lista de mediciones contra esta lista de
especificaciones". Lo que cada uno agrega encima son las verificaciones que no
son una comparacion numerica: que la suma de un perfil cierre, que exista el
estudio que respalda un parametro, que un cambio traiga su comparativo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .modelos import (
    ClaseHallazgo,
    Especificacion,
    Hallazgo,
    Medicion,
    Severidad,
    contrastar,
)
from .valores import Dato


@dataclass(frozen=True, slots=True)
class ParametroAuditado:
    medicion: Medicion
    especificacion: Especificacion | None = None
    severidad_si_desvia: Severidad = Severidad.ALTA


def auditar(
    parametros: Sequence[ParametroAuditado],
    etiquetas: tuple[str, ...] = (),
) -> tuple[Hallazgo, ...]:
    return tuple(
        contrastar(
            p.medicion,
            p.especificacion,
            severidad_si_desvia=p.severidad_si_desvia,
            etiquetas=etiquetas,
        )
        for p in parametros
    )


def respaldo_documental(
    parametro: str,
    referencia: object,
    descripcion_esperada: str,
    etiquetas: tuple[str, ...] = (),
    severidad: Severidad = Severidad.ALTA,
) -> Hallazgo | None:
    """Hallazgo cuando falta el documento que respalda un parametro declarado.

    Un valor sin el estudio que lo produjo es una afirmacion, no un resultado.
    Devuelve None si la referencia esta presente: el silencio es el caso normal.
    """
    presente = isinstance(referencia, Dato) and referencia.presente
    if presente:
        return None
    return Hallazgo(
        parametro=parametro,
        clase=ClaseHallazgo.RESULTADO_NO_SUMINISTRADO,
        severidad=severidad,
        observacion=(
            f"'{parametro}': el expediente no referencia {descripcion_esperada}. "
            f"El valor declarado no se puede rastrear hasta el estudio que lo "
            f"produjo."
        ),
        etiquetas=etiquetas + ("respaldo_documental",),
    )


def campo_ausente(
    nombre: str,
    dato: object,
    etiquetas: tuple[str, ...] = (),
    severidad: Severidad = Severidad.ALTA,
) -> Hallazgo | None:
    """Hallazgo cuando un campo declarativo esperado no aparece en el expediente.

    Devuelve None si el campo esta presente. No infiere, no completa, no asume.
    """
    if isinstance(dato, Dato) and dato.presente:
        return None
    return Hallazgo(
        parametro=nombre,
        clase=ClaseHallazgo.RESULTADO_NO_SUMINISTRADO,
        severidad=severidad,
        observacion=(
            f"'{nombre}' no aparece declarado en el expediente. El agente no lo "
            f"infiere; el evaluador debe requerirlo al solicitante."
        ),
        etiquetas=etiquetas,
    )
