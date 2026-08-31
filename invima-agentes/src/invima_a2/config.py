"""Configuracion y ensamblaje del Agente 2.

Un solo lugar donde se decide que adaptador entra. El flag `offline` cambia todo
el sistema a implementaciones locales sin red ni costo, igual que en el A1.

El log de auditoria y la base de expedientes son los MISMOS del A1 a proposito:
el A2 escribe bajo el mismo radicado, asi que el expediente queda reconstruible
de punta a punta leyendo un solo archivo.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from invima_a1.adaptadores.salida.auditoria_jsonl import AuditLogJSONL
from invima_a1.adaptadores.salida.parser_fake import ParserSidecarMarkdown
from invima_a1.adaptadores.salida.repo_sqlite import RepositorioSQLite

from .adaptadores.salida.expediente_a1_sqlite import ExpedienteA1Repositorio
from .adaptadores.salida.extractor_legal_fake import ExtractorLegalDeterminista
from .aplicacion.validar_y_clasificar import Dependencias

RAIZ = Path(__file__).resolve().parent.parent.parent
DATOS = RAIZ / "data"

MODELO_POR_DEFECTO = "gemini-flash-latest"


def ahora() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class Ajustes:
    offline: bool = True
    modelo: str = MODELO_POR_DEFECTO
    api_key: str | None = None
    directorio_datos: Path = DATOS

    @classmethod
    def desde_entorno(cls, offline: bool, modelo: str | None = None) -> Ajustes:
        return cls(
            offline=offline,
            modelo=modelo or os.getenv("INVIMA_MODELO", MODELO_POR_DEFECTO),
            api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
        )


def construir_dependencias(ajustes: Ajustes) -> tuple[Dependencias, ExpedienteA1Repositorio]:
    datos = ajustes.directorio_datos
    repositorio = RepositorioSQLite(datos / "expedientes.db")
    fuente_a1 = ExpedienteA1Repositorio(repositorio, datos / "fixtures")

    if ajustes.offline:
        extractor = ExtractorLegalDeterminista()
    else:
        if not ajustes.api_key:
            raise RuntimeError(
                "Falta GEMINI_API_KEY. Exportala o corre en modo offline con --offline."
            )
        from invima_a1.adaptadores.salida.extractor_gemini import ExtractorGemini

        extractor = ExtractorGemini(api_key=ajustes.api_key, modelo=ajustes.modelo)

    deps = Dependencias(
        expediente_a1=fuente_a1,
        parser=ParserSidecarMarkdown(),
        extractor=extractor,
        auditoria=AuditLogJSONL(datos / "auditoria.jsonl"),
        reloj=ahora,
    )
    return deps, fuente_a1
