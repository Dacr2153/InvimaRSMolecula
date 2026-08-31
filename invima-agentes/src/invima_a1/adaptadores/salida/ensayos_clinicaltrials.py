"""Consulta de ensayos clinicos en ClinicalTrials.gov (API v2, publica y gratuita).

Verifica que los NCT declarados por el solicitante existan, en que fase estan,
su estatus y si publicaron resultados. Es un cruce de hechos, no un juicio.
"""

from __future__ import annotations

import httpx

from ...puertos.ensayos import RespuestaEnsayo

_BASE = "https://clinicaltrials.gov/api/v2/studies"


class EnsayosClinicalTrials:
    def __init__(self, timeout: float = 20.0) -> None:
        self._timeout = timeout

    def consultar(self, nct_id: str) -> RespuestaEnsayo:
        url = f"https://clinicaltrials.gov/study/{nct_id}"
        try:
            respuesta = httpx.get(f"{_BASE}/{nct_id}", timeout=self._timeout)
        except httpx.HTTPError:
            return RespuestaEnsayo(
                trial_id=nct_id,
                encontrado=False,
                fase=None,
                estatus=None,
                resultados_disponibles=None,
                titulo=None,
                url_fuente=url,
            )

        if respuesta.status_code != 200:
            return RespuestaEnsayo(
                trial_id=nct_id,
                encontrado=False,
                fase=None,
                estatus=None,
                resultados_disponibles=None,
                titulo=None,
                url_fuente=url,
            )

        datos = respuesta.json().get("protocolSection") or {}
        identificacion = datos.get("identificationModule") or {}
        estado = datos.get("statusModule") or {}
        diseno = datos.get("designModule") or {}
        fases = diseno.get("phases") or []

        return RespuestaEnsayo(
            trial_id=nct_id,
            encontrado=True,
            fase=", ".join(fases) if fases else None,
            estatus=estado.get("overallStatus"),
            resultados_disponibles=bool(respuesta.json().get("resultsSection")),
            titulo=identificacion.get("briefTitle"),
            url_fuente=url,
        )
