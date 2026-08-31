"""Manual de Normas Farmacologicas desde CSV local.

Cruce determinista por DCI normalizada: sin coincidencia difusa, sin umbrales.
Si la molecula no esta, no esta, y eso significa molecula nueva. Un evaluador
puede reproducir este resultado abriendo el CSV.
"""

from __future__ import annotations

import csv
from pathlib import Path

from ...domain.servicios.motor_normativo import RegistroNormaFarmacologica
from ...domain.servicios.normalizacion import normalizar_dci


class NormasFarmacologicasCSV:
    def __init__(self, ruta: Path, version: str = "v.2026") -> None:
        self._version = version
        self._indice: dict[str, list[RegistroNormaFarmacologica]] = {}
        with ruta.open(encoding="utf-8", newline="") as archivo:
            for fila in csv.DictReader(archivo):
                registro = RegistroNormaFarmacologica(
                    dci=fila["dci"].strip(),
                    norma=fila["norma"].strip(),
                    forma_farmaceutica=fila.get("forma_farmaceutica", "").strip(),
                    indicacion=fila.get("indicacion", "").strip(),
                )
                self._indice.setdefault(normalizar_dci(registro.dci), []).append(registro)

    @property
    def version(self) -> str:
        return self._version

    def buscar(self, principio_activo: str) -> tuple[RegistroNormaFarmacologica, ...]:
        return tuple(self._indice.get(normalizar_dci(principio_activo), ()))
