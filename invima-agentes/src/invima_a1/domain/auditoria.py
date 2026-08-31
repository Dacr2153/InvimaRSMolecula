"""Eventos de auditoria.

Requisito 7.2 de las reglas: reconstruir que informacion ingreso, que resultado
genero el sistema, quien lo reviso, que cambio y cual fue la decision final.
El log es append-only; nada se edita ni se borra.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class TipoEvento(StrEnum):
    PASO_INICIADO = "PASO_INICIADO"
    PASO_COMPLETADO = "PASO_COMPLETADO"
    ALERTA = "ALERTA"
    LLAMADA_MODELO = "LLAMADA_MODELO"
    CONSULTA_EXTERNA = "CONSULTA_EXTERNA"
    DECISION_HUMANA = "DECISION_HUMANA"
    CAMBIO_ESTADO = "CAMBIO_ESTADO"


@dataclass(frozen=True, slots=True)
class EventoAuditoria:
    momento: datetime
    tipo: TipoEvento
    radicado: str
    accion: str
    resultado: str
    actor: str = "SISTEMA"
    detalles: dict[str, Any] = field(default_factory=dict)

    def a_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.momento.isoformat(),
            "tipo": str(self.tipo),
            "radicado": self.radicado,
            "accion": self.accion,
            "resultado": self.resultado,
            "actor": self.actor,
            "detalles": self.detalles,
        }
