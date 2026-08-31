"""Entrada del Coordinador de Grupos.

Igual que `supervision.py` en el A1, esto es una entrada DISTINTA al sistema y no
un metodo del caso de uso. El agente ni siquiera importa este modulo: no tiene
forma de invocar aquello que podria sacarlo de su propio gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from invima_a1.domain.auditoria import EventoAuditoria, TipoEvento

from ..domain.estados import DecisionHumana, SentidoDecision, estado_resultante
from ..domain.modelos import Dictamen
from ..puertos import AuditLogPort


@dataclass(frozen=True, slots=True)
class RegistrarDecisionCoordinador:
    auditoria: AuditLogPort
    reloj: Callable[[], datetime]

    def ejecutar(
        self,
        dictamen: Dictamen,
        usuario: str,
        sentido: SentidoDecision,
        observaciones: str = "",
        campos_corregidos: tuple[str, ...] = (),
    ) -> Dictamen:
        """Mueve el dictamen con la firma del coordinador, o falla en el intento."""
        decision = DecisionHumana(
            usuario=usuario,
            sentido=sentido,
            momento=self.reloj(),
            observaciones=observaciones,
            campos_corregidos=campos_corregidos,
        )
        destino = estado_resultante(decision)
        dictamen.avanzar_a(destino, decision)

        self.auditoria.registrar(
            EventoAuditoria(
                momento=decision.momento,
                tipo=TipoEvento.DECISION_HUMANA,
                radicado=dictamen.radicado,
                accion=f"Decision del Coordinador de Grupos: {sentido}",
                resultado=str(destino),
                actor=usuario,
                detalles={
                    "observaciones": observaciones,
                    "campos_corregidos": list(campos_corregidos),
                },
            )
        )
        return dictamen
