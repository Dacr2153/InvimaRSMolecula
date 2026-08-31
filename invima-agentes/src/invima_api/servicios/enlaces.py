"""Clasificacion de enlaces de evidencia aportados por el solicitante.

No se descarga ni se valida el contenido del enlace aqui: eso lo hace el agente
contra la fuente publica. Aqui solo se reconoce de que tipo de fuente se trata y
se extrae el identificador cuando la URL lo lleva, para que el agente pueda
verificarlo sin adivinar.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

#: Identificador de estudio en ClinicalTrials.gov.
_NCT = re.compile(r"\bNCT\d{8}\b", re.IGNORECASE)

#: Dominio -> (tipo, etiqueta legible).
_FUENTES: tuple[tuple[str, str, str], ...] = (
    ("clinicaltrials.gov", "ENSAYO_CLINICO", "ClinicalTrials.gov"),
    ("euclinicaltrials.eu", "ENSAYO_CLINICO", "Registro de ensayos clínicos de la UE"),
    ("clinicaltrialsregister.eu", "ENSAYO_CLINICO", "EU Clinical Trials Register"),
    ("ema.europa.eu", "AGENCIA_REFERENCIA", "EMA"),
    ("fda.gov", "AGENCIA_REFERENCIA", "FDA"),
    ("accessdata.fda.gov", "AGENCIA_REFERENCIA", "Drugs@FDA"),
    ("gov.uk", "AGENCIA_REFERENCIA", "MHRA / Reino Unido"),
    ("canada.ca", "AGENCIA_REFERENCIA", "Health Canada"),
    ("tga.gov.au", "AGENCIA_REFERENCIA", "TGA Australia"),
    ("pmda.go.jp", "AGENCIA_REFERENCIA", "PMDA Japón"),
    ("who.int", "AGENCIA_REFERENCIA", "OMS"),
    ("pubmed.ncbi.nlm.nih.gov", "PUBLICACION", "PubMed"),
    ("ncbi.nlm.nih.gov", "PUBLICACION", "NCBI"),
    ("doi.org", "PUBLICACION", "DOI"),
)

ESQUEMAS_ADMITIDOS = frozenset({"http", "https"})


class EnlaceInvalido(ValueError):
    """La URL no es utilizable como evidencia verificable."""


def clasificar(url: str) -> tuple[str, str, str]:
    """Devuelve (tipo, titulo sugerido, referencia).

    Solo se aceptan http y https: un enlace de evidencia tiene que poder abrirlo
    el evaluador desde su navegador.
    """
    limpia = url.strip()
    if not limpia:
        raise EnlaceInvalido("El enlace no puede estar vacío")

    partes = urlparse(limpia)
    if partes.scheme.lower() not in ESQUEMAS_ADMITIDOS:
        raise EnlaceInvalido(
            f"Solo se admiten enlaces http o https; se recibió '{partes.scheme or limpia[:20]}'"
        )
    if not partes.netloc:
        raise EnlaceInvalido("El enlace no tiene un dominio válido")

    dominio = partes.netloc.lower().removeprefix("www.")
    for sufijo, tipo, etiqueta in _FUENTES:
        if dominio == sufijo or dominio.endswith("." + sufijo):
            referencia = ""
            if tipo == "ENSAYO_CLINICO":
                encontrado = _NCT.search(limpia)
                referencia = encontrado.group(0).upper() if encontrado else ""
            titulo = f"{etiqueta} — {referencia}" if referencia else etiqueta
            return tipo, titulo, referencia

    return "OTRO", dominio, ""


def folio_de_enlaces(enlaces: list[dict[str, str]]) -> str:
    """Arma el folio Markdown que el agente lee.

    Los identificadores NCT quedan escritos de forma explicita porque el A1 ya
    los detecta y los verifica contra ClinicalTrials.gov: aportar el enlace basta
    para que el estudio se verifique solo.
    """
    lineas = [
        "<!-- pagina: 1 -->",
        "# Evidencia aportada como enlace público",
        "",
        "Enlaces declarados por el solicitante. No sustituyen folios obligatorios;",
        "son fuentes públicas para verificación directa del evaluador.",
        "",
        "| Tipo | Referencia | Enlace |",
        "| --- | --- | --- |",
    ]
    for enlace in enlaces:
        referencia = enlace.get("referencia") or "-"
        lineas.append(f"| {enlace['tipo']} | {referencia} | {enlace['url']} |")

    referencias = [e["referencia"] for e in enlaces if e.get("referencia")]
    if referencias:
        lineas += ["", f"Identificadores NCT declarados: {', '.join(sorted(set(referencias)))}"]
    return "\n".join(lineas) + "\n"


__all__ = ["EnlaceInvalido", "clasificar", "folio_de_enlaces"]
