"""Puerto de lectura de la evidencia cientifica (Modulos 4, 5 y 7)."""

from __future__ import annotations

from typing import Protocol

from ..domain.modulo45 import ExpedienteEvidencia


class ExpedienteEvidenciaPort(Protocol):
    def leer(self, radicado: str) -> ExpedienteEvidencia:
        """Construye el agregado de evidencia para un radicado.

        Contrato que toda implementacion respeta: un campo que no aparece en el
        expediente se devuelve como Dato.ausente. En evidencia clinica la
        tentacion de completar es mayor que en ningun otro modulo -- el valor
        tipico de la clase terapeutica siempre esta a mano -- y es exactamente
        lo que convertiria la auditoria en ficcion.
        """
        ...

    @property
    def procedencia(self) -> str:
        """Como se obtuvo el expediente (fixture, parser local, modelo)."""
        ...
