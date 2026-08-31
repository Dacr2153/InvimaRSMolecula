"""Ensamblaje de dependencias con persistencia en PostgreSQL.

Modulo aparte a proposito: `config.py` es el ensamblaje de la CLI offline y no
debe adquirir una dependencia de psycopg. Aqui se reusa todo lo que ya decide
`construir_dependencias` (parser, extractor, tarifario, agencias, ensayos,
normas, reloj) y solo se cambian las dos piezas de persistencia.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from uuid import UUID

from .adaptadores.salida.auditoria_postgres import AuditLogPostgres
from .adaptadores.salida.repo_postgres import (
    FabricaConexiones,
    RepositorioPostgres,
    conexiones_desde_dsn,
)
from .aplicacion.procesar_radicacion import Dependencias
from .config import Ajustes, construir_dependencias


def construir_dependencias_postgres(
    ajustes: Ajustes,
    dsn: str | None = None,
    conexiones: FabricaConexiones | None = None,
    solicitud_id: UUID | str | None = None,
    carpeta_dossier: Path | str = "",
) -> Dependencias:
    """Mismas dependencias que `construir_dependencias`, con repositorio y
    auditoria en PostgreSQL.

    Se acepta `dsn` (conexiones sueltas) o `conexiones` (una fabrica ya
    existente, tipicamente `pool.connection` de la API). Uno de los dos es
    obligatorio.
    """
    if conexiones is None:
        if not dsn:
            raise ValueError(
                "construir_dependencias_postgres necesita un dsn o una fabrica "
                "de conexiones"
            )
        conexiones = conexiones_desde_dsn(dsn)

    base = construir_dependencias(ajustes)
    return replace(
        base,
        repositorio=RepositorioPostgres(
            conexiones, solicitud_id=solicitud_id, carpeta_dossier=carpeta_dossier
        ),
        auditoria=AuditLogPostgres(conexiones),
    )


__all__ = ["construir_dependencias_postgres"]
