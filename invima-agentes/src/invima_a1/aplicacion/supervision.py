"""Gate de supervision humana.

Entrada distinta al sistema, a proposito. El caso de uso del agente no importa
este modulo ni puede invocarlo: la unica forma de mover un expediente desde
PENDIENTE_VALIDACION_HUMANA es que alguien, con nombre, ejecute esto.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..domain.auditoria import EventoAuditoria, TipoEvento
from ..domain.errores import TransicionIlegalError
from ..domain.estados import DecisionHumana, SentidoDecision
from ..puertos import AuditLogPort, RepositorioExpedientePort


@dataclass(frozen=True, slots=True)
class RegistrarDecisionHumana:
    repositorio: RepositorioExpedientePort
    auditoria: AuditLogPort
    reloj: Callable[[], datetime]

    def ejecutar(
        self,
        radicado: str,
        usuario: str,
        sentido: SentidoDecision,
        observaciones: str = "",
        campos_corregidos: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        cargado = self.repositorio.cargar(radicado)
        if cargado is None:
            raise TransicionIlegalError(f"No existe el expediente {radicado}")

        expediente, payload = cargado
        decision = DecisionHumana(
            usuario=usuario,
            sentido=sentido,
            momento=self.reloj(),
            observaciones=observaciones,
            campos_corregidos=campos_corregidos,
        )
        expediente.registrar_decision_humana(decision, self.reloj())

        for evento in expediente.eventos[-2:]:
            self.auditoria.registrar(evento)

        payload["radicacion"]["estado"] = str(expediente.estado)
        payload["supervision_humana"] = {
            "estado": f"DECIDIDO POR EL EVALUADOR ({decision.sentido})",
            "advertencia": payload["supervision_humana"]["advertencia"],
            "checklist_evaluador": {
                "datos_extraidos_validados": True,
                "busqueda_internacional_confirmada": True,
                "enrutamiento_aprobado": sentido is not SentidoDecision.DEVOLVER,
            },
            "usuario_responsable": decision.usuario,
            "sentido_decision": str(decision.sentido),
            "firma_timestamp": decision.momento.isoformat(),
            "campos_corregidos": list(decision.campos_corregidos),
            "observaciones": decision.observaciones,
        }
        payload["seguridad_y_trazabilidad"]["auditoria_log"] = [
            e.a_dict() for e in expediente.eventos
        ]

        self.repositorio.guardar(expediente, payload)
        self.auditoria.registrar(
            EventoAuditoria(
                momento=self.reloj(),
                tipo=TipoEvento.PASO_COMPLETADO,
                radicado=radicado,
                accion="Cierre del agente A1-RCE",
                resultado=f"Expediente en estado {expediente.estado}",
                actor=usuario,
            )
        )
        return payload


__all__ = ["RegistrarDecisionHumana", "SentidoDecision"]
