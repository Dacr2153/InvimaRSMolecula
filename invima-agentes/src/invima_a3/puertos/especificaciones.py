"""Puerto de especificaciones de fuente normativa.

Cuando el expediente no declara el limite de un parametro, el agente puede
buscarlo en una fuente citable (farmacopea, norma tecnica). Lo que no puede es
inventarlo: una implementacion que no encuentre el parametro devuelve None, y
el hallazgo sale como ESPECIFICACION_NO_DECLARADA.
"""

from __future__ import annotations

from typing import Protocol

from ..domain.modelos import Especificacion


class EspecificacionesPort(Protocol):
    @property
    def version(self) -> str:
        """Edicion de la fuente consultada, para que quede en la traza."""
        ...

    def buscar(self, parametro: str) -> Especificacion | None:
        """Cruce determinista por nombre de parametro. Sin coincidencia difusa."""
        ...
