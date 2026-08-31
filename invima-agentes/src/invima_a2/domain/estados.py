"""Maquina de estados del dictamen del A2.

Misma garantia que el A1, aplicada a la etapa siguiente: no existe camino que
lleve un expediente a REPARTIDO sin que un servidor publico haya registrado su
decision. El agente clasifica y recomienda; el Coordinador de Grupos reparte.

`DecisionHumana` se reusa tal cual del A1 en vez de redefinirse, para que la
firma del coordinador quede en el log con la misma forma que la del evaluador y
el expediente se pueda reconstruir leyendo un solo archivo.
"""

from __future__ import annotations

from enum import StrEnum

from invima_a1.domain.estados import DecisionHumana, SentidoDecision

from .errores import TransicionIlegalError


class EstadoDictamen(StrEnum):
    RECIBIDO_DE_A1 = "RECIBIDO_DE_A1"
    LEGAL_VALIDADO = "LEGAL_VALIDADO"
    CLASIFICADO = "CLASIFICADO"
    PENDIENTE_VALIDACION_COORDINADOR = "PENDIENTE_VALIDACION_COORDINADOR"
    RETENIDO_POR_ALERTA_CRITICA = "RETENIDO_POR_ALERTA_CRITICA"
    REPARTIDO = "REPARTIDO"
    DEVUELTO_PARA_SUBSANACION = "DEVUELTO_PARA_SUBSANACION"


#: Lo que el agente puede hacer solo. Notese que los dos estados de entrega
#: (PENDIENTE_VALIDACION_COORDINADOR y RETENIDO_POR_ALERTA_CRITICA) son terminales
#: para el agente: de ahi no sale ninguna flecha automatica.
TRANSICIONES_AUTOMATICAS: dict[EstadoDictamen, frozenset[EstadoDictamen]] = {
    EstadoDictamen.RECIBIDO_DE_A1: frozenset({EstadoDictamen.LEGAL_VALIDADO}),
    EstadoDictamen.LEGAL_VALIDADO: frozenset({EstadoDictamen.CLASIFICADO}),
    EstadoDictamen.CLASIFICADO: frozenset(
        {
            EstadoDictamen.PENDIENTE_VALIDACION_COORDINADOR,
            EstadoDictamen.RETENIDO_POR_ALERTA_CRITICA,
        }
    ),
    EstadoDictamen.PENDIENTE_VALIDACION_COORDINADOR: frozenset(),
    EstadoDictamen.RETENIDO_POR_ALERTA_CRITICA: frozenset(),
    EstadoDictamen.REPARTIDO: frozenset(),
    EstadoDictamen.DEVUELTO_PARA_SUBSANACION: frozenset(),
}

#: Solo se abren con una DecisionHumana firmada.
#: Un expediente retenido por alerta critica no puede repartirse por inercia: el
#: coordinador tiene que levantar la retencion a mano y quedar registrado.
TRANSICIONES_CON_DECISION_HUMANA: dict[EstadoDictamen, frozenset[EstadoDictamen]] = {
    EstadoDictamen.PENDIENTE_VALIDACION_COORDINADOR: frozenset(
        {EstadoDictamen.REPARTIDO, EstadoDictamen.DEVUELTO_PARA_SUBSANACION}
    ),
    EstadoDictamen.RETENIDO_POR_ALERTA_CRITICA: frozenset(
        {EstadoDictamen.REPARTIDO, EstadoDictamen.DEVUELTO_PARA_SUBSANACION}
    ),
}


def estado_resultante(decision: DecisionHumana) -> EstadoDictamen:
    if decision.sentido is SentidoDecision.DEVOLVER:
        return EstadoDictamen.DEVUELTO_PARA_SUBSANACION
    return EstadoDictamen.REPARTIDO


def validar_transicion(
    origen: EstadoDictamen,
    destino: EstadoDictamen,
    decision: DecisionHumana | None = None,
) -> None:
    """Autoriza o rechaza un cambio de estado del dictamen."""
    if destino in TRANSICIONES_AUTOMATICAS.get(origen, frozenset()):
        return

    if destino in TRANSICIONES_CON_DECISION_HUMANA.get(origen, frozenset()):
        if decision is None:
            raise TransicionIlegalError(
                f"La transicion {origen} -> {destino} exige la decision del "
                f"Coordinador de Grupos. El sistema no puede adoptarla de forma "
                f"autonoma (art. 7.1, Resolucion 2026025611)."
            )
        return

    raise TransicionIlegalError(f"Transicion no contemplada: {origen} -> {destino}")


__all__ = [
    "EstadoDictamen",
    "DecisionHumana",
    "SentidoDecision",
    "TRANSICIONES_AUTOMATICAS",
    "TRANSICIONES_CON_DECISION_HUMANA",
    "estado_resultante",
    "validar_transicion",
]
