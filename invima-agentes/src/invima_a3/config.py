"""Configuracion y ensamblaje de dependencias del Agente 3.

Igual que en el A1: un solo lugar donde se decide que adaptador entra. El modo
por defecto es offline -- lectura determinista del fixture -- porque asi corren
las pruebas y asi se demuestra ante el jurado sin gastar credito ni depender de
la red.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from invima_a1.adaptadores.salida.auditoria_jsonl import AuditLogJSONL

from .adaptadores.salida.expediente_calidad_markdown import LectorModulo3Markdown
from .puertos import AuditLogPort
from .puertos.especificaciones import EspecificacionesPort
from .puertos.expediente_calidad import ExpedienteCalidadPort

RAIZ = Path(__file__).resolve().parent.parent.parent
DATOS = RAIZ / "data"
FIXTURES = DATOS / "fixtures"


def ahora() -> datetime:
    return datetime.now(UTC)


class SinEspecificacionesNormativas:
    """Fuente normativa inerte para modo offline.

    Devuelve None siempre, a proposito: un parametro sin especificacion en el
    dossier debe verse como tal en el tablero. Rellenarlo con un limite tipico
    de la clase seria fabricar el criterio contra el que se audita.
    """

    @property
    def version(self) -> str:
        return "Sin fuente normativa cargada (modo offline)"

    def buscar(self, parametro: str) -> None:
        return None


@dataclass(frozen=True, slots=True)
class Dependencias:
    lector: ExpedienteCalidadPort
    auditoria: AuditLogPort
    especificaciones: EspecificacionesPort


def construir_dependencias(
    ruta_modulo3: Path,
    ruta_log: Path | None = None,
) -> Dependencias:
    return Dependencias(
        lector=LectorModulo3Markdown(ruta_modulo3),
        auditoria=AuditLogJSONL(ruta_log or DATOS / "cache" / "auditoria_a3.jsonl"),
        especificaciones=SinEspecificacionesNormativas(),
    )
