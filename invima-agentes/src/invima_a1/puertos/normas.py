"""Puerto de consulta al Manual de Normas Farmacologicas de Colombia."""

from __future__ import annotations

from typing import Protocol

from ..domain.servicios.motor_normativo import RegistroNormaFarmacologica


class NormasFarmacologicasPort(Protocol):
    @property
    def version(self) -> str: ...

    def buscar(self, principio_activo: str) -> tuple[RegistroNormaFarmacologica, ...]:
        """Cruce determinista por DCI normalizada. Sin coincidencia difusa: si no
        esta, no esta, y eso significa molecula nueva."""
        ...
