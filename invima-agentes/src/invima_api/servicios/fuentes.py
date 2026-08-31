"""Extraccion de las fuentes externas a partir del payload del A1.

De donde sale cada cosa, y por que:

El bloque `validaciones_internacionales` guarda el CONTRASTE (que indicacion se
pide aca contra cual se aprobo alla) pero no guarda la URL consultada: la URL
queda en el log de auditoria, en los eventos CONSULTA_EXTERNA que emiten los
pasos 5 y 6. Por eso este modulo cruza ambos: el evento aporta la fuente, su URL
y si se encontro; el contraste aporta el titulo y la observacion.

En modo offline los eventos salen con `encontrada=False` y la URL de consulta.
Eso es exactamente lo que el contrato pide mostrar: no se consulto la fuente,
solo se ofrece el enlace. No se fabrica un hallazgo.
"""

from __future__ import annotations

import re
from typing import Any

_PAISES = {
    "FDA": "Estados Unidos",
    "EMA": "Unión Europea",
    "MHRA": "Reino Unido",
    "HEALTH CANADA": "Canadá",
    "TGA": "Australia",
    "PMDA": "Japón",
    "CLINICALTRIALS.GOV": "Estados Unidos",
}

_RE_CONSULTA_AGENCIA = re.compile(r"^Consulta a (?P<agencia>.+)$")
_RE_ENSAYO = re.compile(r"^Verificacion de ensayo clinico (?P<nct>NCT\d+)$")

_TIPO_APROBACION = "Aprobación sanitaria"
_TIPO_ENSAYO = "Ensayo clínico registrado"


def _contrastes_por_agencia(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    bloque = (payload.get("validaciones_internacionales") or {}).get(
        "reporte_coincidencia_internacional"
    ) or {}
    salida: dict[str, dict[str, Any]] = {}
    for contraste in bloque.get("contrastes") or []:
        agencia = str(contraste.get("agencia", "")).strip().upper()
        if agencia:
            salida[agencia] = contraste
    return salida


def _eventos(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return list(
        (payload.get("seguridad_y_trazabilidad") or {}).get("auditoria_log") or []
    )


def extraer_fuentes(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Devuelve las fuentes externas del expediente, sin duplicados.

    La clave de unicidad es (fuente, titulo), la misma que impone la tabla
    `fuentes_externas`.
    """
    contrastes = _contrastes_por_agencia(payload)
    vistas: set[tuple[str, str]] = set()
    fuentes: list[dict[str, Any]] = []

    def agregar(registro: dict[str, Any]) -> None:
        clave = (registro["fuente"], registro["titulo"])
        if clave in vistas:
            return
        vistas.add(clave)
        fuentes.append(registro)

    for evento in _eventos(payload):
        if evento.get("tipo") != "CONSULTA_EXTERNA":
            continue
        accion = str(evento.get("accion", ""))
        resultado = str(evento.get("resultado", ""))
        url = str((evento.get("detalles") or {}).get("url", ""))

        coincidencia = _RE_CONSULTA_AGENCIA.match(accion)
        if coincidencia:
            agencia = coincidencia.group("agencia").strip().upper()
            contraste = contrastes.get(agencia, {})
            titulo = (
                contraste.get("indicacion_aprobada")
                or f"Consulta de aprobación en {agencia}"
            )
            observaciones = " ".join(
                parte
                for parte in (resultado, contraste.get("observacion") or "")
                if parte
            )
            agregar(
                {
                    "fuente": agencia,
                    "titulo": str(titulo),
                    "tipo": _TIPO_APROBACION,
                    "pais": _PAISES.get(agencia, ""),
                    "fecha": "",
                    "url": url,
                    "encontrada": resultado.strip().lower().startswith("encontrada"),
                    "observaciones": observaciones,
                }
            )
            continue

        ensayo = _RE_ENSAYO.match(accion)
        if ensayo:
            nct = ensayo.group("nct")
            agregar(
                {
                    "fuente": "ClinicalTrials.gov",
                    "titulo": nct,
                    "tipo": _TIPO_ENSAYO,
                    "pais": _PAISES["CLINICALTRIALS.GOV"],
                    "fecha": "",
                    "url": url,
                    "encontrada": "no encontrado" not in resultado.lower(),
                    "observaciones": resultado,
                }
            )

    # Aprobaciones que el solicitante declaro y que nunca generaron una consulta
    # (una agencia fuera de la matriz de puertos, por ejemplo MHRA). Se listan
    # igual, marcadas como no verificadas: el evaluador debe saber que existen.
    for agencia, contraste in contrastes.items():
        titulo = contraste.get("indicacion_aprobada") or f"Aprobación declarada en {agencia}"
        if (agencia, str(titulo)) in vistas:
            continue
        agregar(
            {
                "fuente": agencia,
                "titulo": str(titulo),
                "tipo": _TIPO_APROBACION,
                "pais": _PAISES.get(agencia, ""),
                "fecha": "",
                "url": "",
                "encontrada": False,
                "observaciones": (
                    "Aprobación declarada por el solicitante y no verificada en la "
                    "fuente. " + str(contraste.get("observacion") or "")
                ).strip(),
            }
        )

    return fuentes


__all__ = ["extraer_fuentes"]
