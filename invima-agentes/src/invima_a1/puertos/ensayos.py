"""Puerto de consulta de ensayos clinicos registrados (ClinicalTrials.gov)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RespuestaEnsayo:
    trial_id: str
    encontrado: bool
    fase: str | None
    estatus: str | None
    resultados_disponibles: bool | None
    titulo: str | None
    url_fuente: str


class EnsayosClinicosPort(Protocol):
    def consultar(self, nct_id: str) -> RespuestaEnsayo: ...
