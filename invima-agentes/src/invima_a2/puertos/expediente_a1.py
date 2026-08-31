"""Contrato de entrada: como llega al A2 lo que produjo el A1.

El A2 no vuelve a parsear el dossier ni a extraer el formulario. Recibe el
payload que el A1 ya construyo y validado, y solo agrega lo que el A1 no mira:
los documentos juridicos del Modulo 1 y la taxonomia del producto.

Que esto sea un puerto y no una llamada directa significa que el A1 puede correr
en otra maquina, en otro momento, o ser reemplazado, sin que el A2 se entere.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class ExpedienteA1Port(Protocol):
    def cargar(self, radicado: str) -> dict[str, Any]:
        """Devuelve el payload que el A1 entrego para ese radicado.

        Levanta KeyError si el radicado no fue procesado por el A1. El A2 no
        inventa un expediente vacio: si el A1 no paso por ahi, no hay que validar.
        """
        ...

    def carpeta_dossier(self, radicado: str) -> Path:
        """Ubicacion de los folios, para leer los documentos legales del Modulo 1."""
        ...
