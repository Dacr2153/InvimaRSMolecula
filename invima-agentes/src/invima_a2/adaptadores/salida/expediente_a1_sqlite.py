"""Lee lo que el A1 dejo persistido, sin acoplarse a su modelo de dominio.

El A2 solo necesita el payload JSON y la ubicacion de los folios. Reusar el
repositorio del A1 evita duplicar la base y, sobre todo, garantiza que el A2
valide exactamente el mismo expediente que el evaluador vio.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from invima_a1.puertos.repositorio import RepositorioExpedientePort


class ExpedienteA1Repositorio:
    def __init__(self, repositorio: RepositorioExpedientePort, raiz_dossieres: Path) -> None:
        self._repo = repositorio
        self._raiz = raiz_dossieres
        self._carpetas: dict[str, Path] = {}

    def registrar_carpeta(self, radicado: str, carpeta: Path) -> None:
        """Asocia un radicado a la carpeta de folios que lo origino."""
        self._carpetas[radicado] = carpeta

    def cargar(self, radicado: str) -> dict[str, Any]:
        registro = self._repo.cargar(radicado)
        if registro is None:
            raise KeyError(
                f"El radicado {radicado} no fue procesado por el A1. El A2 no "
                f"valida expedientes que no pasaron por radicacion."
            )
        _, payload = registro
        return payload

    def carpeta_dossier(self, radicado: str) -> Path:
        if radicado in self._carpetas:
            return self._carpetas[radicado]
        return self._raiz


class ExpedienteA1EnMemoria:
    """Doble para pruebas y para encadenar A1 y A2 en una sola corrida."""

    def __init__(self) -> None:
        self._payloads: dict[str, dict[str, Any]] = {}
        self._carpetas: dict[str, Path] = {}

    def registrar(self, radicado: str, payload: dict[str, Any], carpeta: Path) -> None:
        self._payloads[radicado] = payload
        self._carpetas[radicado] = carpeta

    def cargar(self, radicado: str) -> dict[str, Any]:
        if radicado not in self._payloads:
            raise KeyError(f"El radicado {radicado} no fue procesado por el A1")
        return self._payloads[radicado]

    def carpeta_dossier(self, radicado: str) -> Path:
        return self._carpetas[radicado]
