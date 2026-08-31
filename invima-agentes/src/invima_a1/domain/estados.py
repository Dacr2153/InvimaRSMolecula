"""Maquina de estados del expediente.

Aqui vive la garantia mas importante del sistema: no existe camino que lleve un
expediente a ENRUTADO sin que un servidor publico haya registrado su decision.
El agente no tiene la capacidad tecnica de auto-aprobar.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from .errores import TransicionIlegalError


class EstadoExpediente(StrEnum):
    RECIBIDO = "RECIBIDO"
    INGESTADO = "INGESTADO"
    METADATOS_EXTRAIDOS = "METADATOS_EXTRAIDOS"
    PAGO_VALIDADO = "PAGO_VALIDADO"
    RELIANCE_COMPLETADO = "RELIANCE_COMPLETADO"
    NORMAS_EVALUADAS = "NORMAS_EVALUADAS"
    RUTA_RECOMENDADA = "RUTA_RECOMENDADA"
    PENDIENTE_VALIDACION_HUMANA = "PENDIENTE_VALIDACION_HUMANA"
    ENRUTADO = "ENRUTADO"
    SUSPENDIDO_POR_INCONSISTENCIA = "SUSPENDIDO_POR_INCONSISTENCIA"
    DEVUELTO_POR_EVALUADOR = "DEVUELTO_POR_EVALUADOR"


#: Transiciones que el agente puede ejecutar por si solo.
#: Notese que PENDIENTE_VALIDACION_HUMANA es un estado terminal para el agente:
#: de ahi no sale ninguna flecha. Solo una decision humana lo mueve.
TRANSICIONES_AUTOMATICAS: dict[EstadoExpediente, frozenset[EstadoExpediente]] = {
    EstadoExpediente.RECIBIDO: frozenset({EstadoExpediente.INGESTADO}),
    EstadoExpediente.INGESTADO: frozenset({EstadoExpediente.METADATOS_EXTRAIDOS}),
    EstadoExpediente.METADATOS_EXTRAIDOS: frozenset(
        {
            EstadoExpediente.PAGO_VALIDADO,
            EstadoExpediente.SUSPENDIDO_POR_INCONSISTENCIA,
        }
    ),
    EstadoExpediente.PAGO_VALIDADO: frozenset({EstadoExpediente.RELIANCE_COMPLETADO}),
    EstadoExpediente.RELIANCE_COMPLETADO: frozenset({EstadoExpediente.NORMAS_EVALUADAS}),
    EstadoExpediente.NORMAS_EVALUADAS: frozenset({EstadoExpediente.RUTA_RECOMENDADA}),
    EstadoExpediente.RUTA_RECOMENDADA: frozenset(
        {EstadoExpediente.PENDIENTE_VALIDACION_HUMANA}
    ),
    EstadoExpediente.PENDIENTE_VALIDACION_HUMANA: frozenset(),
    EstadoExpediente.SUSPENDIDO_POR_INCONSISTENCIA: frozenset(),
    EstadoExpediente.ENRUTADO: frozenset(),
    EstadoExpediente.DEVUELTO_POR_EVALUADOR: frozenset(),
}

#: Transiciones que solo se abren cuando hay una DecisionHumana firmada.
TRANSICIONES_CON_DECISION_HUMANA: dict[EstadoExpediente, frozenset[EstadoExpediente]] = {
    EstadoExpediente.PENDIENTE_VALIDACION_HUMANA: frozenset(
        {
            EstadoExpediente.ENRUTADO,
            EstadoExpediente.DEVUELTO_POR_EVALUADOR,
        }
    ),
    EstadoExpediente.SUSPENDIDO_POR_INCONSISTENCIA: frozenset(
        {EstadoExpediente.DEVUELTO_POR_EVALUADOR}
    ),
}


class SentidoDecision(StrEnum):
    APROBAR_ENRUTAMIENTO = "APROBAR_ENRUTAMIENTO"
    CORREGIR_Y_APROBAR = "CORREGIR_Y_APROBAR"
    DEVOLVER = "DEVOLVER"


@dataclass(frozen=True, slots=True)
class DecisionHumana:
    """Registro de la intervencion del servidor publico competente.

    Sin una instancia de esto no hay enrutamiento posible. El campo `usuario` no
    admite vacio: la responsabilidad por la decision final tiene nombre propio.
    """

    usuario: str
    sentido: SentidoDecision
    momento: datetime
    observaciones: str = ""
    campos_corregidos: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.usuario or not self.usuario.strip():
            raise TransicionIlegalError(
                "Una decision humana requiere identificar al servidor publico responsable"
            )

    @property
    def estado_resultante(self) -> EstadoExpediente:
        if self.sentido is SentidoDecision.DEVOLVER:
            return EstadoExpediente.DEVUELTO_POR_EVALUADOR
        return EstadoExpediente.ENRUTADO


def validar_transicion(
    origen: EstadoExpediente,
    destino: EstadoExpediente,
    decision: DecisionHumana | None = None,
) -> None:
    """Autoriza o rechaza un cambio de estado.

    Levanta TransicionIlegalError si el agente intenta avanzar por su cuenta hacia
    un estado que exige decision humana.
    """
    if destino in TRANSICIONES_AUTOMATICAS.get(origen, frozenset()):
        return

    permitidas_con_humano = TRANSICIONES_CON_DECISION_HUMANA.get(origen, frozenset())
    if destino in permitidas_con_humano:
        if decision is None:
            raise TransicionIlegalError(
                f"La transicion {origen} -> {destino} exige la decision de un servidor "
                f"publico competente. El sistema no puede adoptarla de forma autonoma "
                f"(art. 7.1, Resolucion 2026025611)."
            )
        return

    raise TransicionIlegalError(f"Transicion no contemplada: {origen} -> {destino}")
