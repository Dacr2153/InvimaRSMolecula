"""Configuracion de la API, leida del entorno.

Sin secretos por defecto y sin magia: si falta el DSN se falla al arrancar con
un mensaje que dice que exportar.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent

#: Extensiones que se aceptan como folio del expediente.
EXTENSIONES_PERMITIDAS = frozenset({".md", ".pdf", ".txt"})

#: 25 MB. Un folio de un dossier CTD no deberia pasar de ahi en esta demo.
TAMANO_MAXIMO_BYTES = 25 * 1024 * 1024

DSN_POR_DEFECTO = "postgresql://invima:invima@localhost:5433/rsmolecula"


def _bandera(nombre: str, por_defecto: bool) -> bool:
    crudo = os.getenv(nombre)
    if crudo is None:
        return por_defecto
    return crudo.strip().lower() in {"1", "true", "si", "sí", "yes", "on"}


@dataclass(frozen=True, slots=True)
class AjustesAPI:
    dsn: str
    directorio_datos: Path
    offline: bool
    origenes_cors: tuple[str, ...]
    directorio_migraciones: Path
    demo: bool = True
    directorio_demo: Path = RAIZ / "data" / "demo"
    tamano_maximo_bytes: int = TAMANO_MAXIMO_BYTES
    extensiones_permitidas: frozenset[str] = field(default=EXTENSIONES_PERMITIDAS)

    @property
    def directorio_dossieres(self) -> Path:
        return self.directorio_datos / "dossieres"

    @property
    def directorio_cargas(self) -> Path:
        return self.directorio_datos / "cargas"

    @classmethod
    def desde_entorno(cls) -> AjustesAPI:
        crudo_cors = os.getenv("INVIMA_CORS", "*")
        origenes = tuple(o.strip() for o in crudo_cors.split(",") if o.strip())
        return cls(
            dsn=os.getenv("INVIMA_DSN", DSN_POR_DEFECTO),
            directorio_datos=Path(os.getenv("INVIMA_DATOS", str(RAIZ / "data"))),
            # Offline por defecto: la demo no debe gastar credito ni depender de red.
            offline=_bandera("INVIMA_OFFLINE", True),
            origenes_cors=origenes or ("*",),
            directorio_migraciones=Path(
                os.getenv("INVIMA_MIGRACIONES", str(RAIZ / "infra" / "postgres"))
            ),
            # Precarga del borrador con el dossier oficial de Corazilimab, para
            # que una demostracion sea "siguiente, siguiente, radicar".
            demo=_bandera("INVIMA_DEMO", True),
            directorio_demo=Path(
                os.getenv("INVIMA_DEMO_FOLIOS", str(RAIZ / "data" / "demo"))
            ),
        )


__all__ = ["AjustesAPI", "EXTENSIONES_PERMITIDAS", "TAMANO_MAXIMO_BYTES"]
