"""Puerto de lectura del Modulo 3.

Separa "leer el dossier" de "auditarlo". El nucleo del A3 nunca toca un PDF ni
un modelo: recibe un ExpedienteCalidad ya construido y trazado, y esa es la
razon por la que toda la logica de auditoria es testeable sin red y sin gasto.
"""

from __future__ import annotations

from typing import Protocol

from ..domain.modulo3 import ExpedienteCalidad


class ExpedienteCalidadPort(Protocol):
    def leer(self, radicado: str) -> ExpedienteCalidad:
        """Construye el agregado de calidad para un radicado.

        Contrato que toda implementacion respeta: un campo que no aparece en el
        expediente se devuelve como Dato.ausente, jamas se infiere ni se completa
        con un valor tipico de la clase terapeutica.
        """
        ...

    @property
    def procedencia(self) -> str:
        """Como se obtuvo el expediente (fixture, parser local, modelo)."""
        ...
