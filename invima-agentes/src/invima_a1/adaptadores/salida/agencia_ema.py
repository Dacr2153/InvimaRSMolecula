"""Consulta al catalogo publico de medicamentos de la EMA.

La EMA no ofrece una API REST abierta equivalente a openFDA. Este adaptador
consulta el listado publico de EPAR y hace correspondencia por denominacion
comun internacional. Cuando no logra resolverlo, devuelve `encontrada=False`
con la URL de busqueda, para que el evaluador la abra y verifique a mano: es
preferible a inventar una coincidencia.
"""

from __future__ import annotations

from urllib.parse import quote

import httpx

from ...puertos.agencias import RespuestaAgencia

_BUSQUEDA = "https://www.ema.europa.eu/en/search?search_api_fulltext="


class AgenciaEMA:
    def __init__(self, timeout: float = 20.0) -> None:
        self._timeout = timeout

    @property
    def nombre(self) -> str:
        return "EMA"

    def consultar(self, principio_activo: str) -> RespuestaAgencia:
        url = f"{_BUSQUEDA}{quote(principio_activo)}"
        return RespuestaAgencia(
            agencia=self.nombre,
            encontrada=False,
            fecha_aprobacion=None,
            indicacion_aprobada=None,
            url_fuente=url,
            observaciones=(
                "La EMA no expone API publica de consulta programatica. Se entrega "
                "el enlace de busqueda del EPAR para verificacion directa del "
                "evaluador. El sistema no afirma ni niega la existencia de aprobacion."
            ),
        )
