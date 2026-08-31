"""Configuracion y ensamblaje de dependencias del Agente 4.

Modo offline por defecto: lectura determinista del fixture, sin red y sin
consumir credito. Asi corren las pruebas y asi se demuestra ante el jurado.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from invima_a1.adaptadores.salida.auditoria_jsonl import AuditLogJSONL

from .adaptadores.salida.expediente_evidencia_markdown import LectorEvidenciaMarkdown
from .puertos import AuditLogPort
from .puertos.expediente_evidencia import ExpedienteEvidenciaPort

RAIZ = Path(__file__).resolve().parent.parent.parent
DATOS = RAIZ / "data"
FIXTURES = DATOS / "fixtures"


def ahora() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class Dependencias:
    lector: ExpedienteEvidenciaPort
    auditoria: AuditLogPort


def construir_dependencias(
    ruta_evidencia: Path,
    ruta_log: Path | None = None,
) -> Dependencias:
    return Dependencias(
        lector=LectorEvidenciaMarkdown(ruta_evidencia),
        auditoria=AuditLogJSONL(ruta_log or DATOS / "cache" / "auditoria_a4.jsonl"),
    )
