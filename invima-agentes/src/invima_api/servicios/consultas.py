"""Busqueda en el corpus normativo.

Recupera y cita; no redacta criterio. El puntaje es un solapamiento de terminos
entre la pregunta del evaluador y (pregunta + etiquetas) de cada entrada. Si
nada supera el umbral, la respuesta es que no hay entrada, con cita vacia.
Nunca se inventa una respuesta.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

SIN_COINCIDENCIA = "No hay una entrada en el corpus normativo para esa consulta"

#: Umbral minimo de terminos compartidos. Con uno solo se cuela cualquier cosa.
UMBRAL = 2

_VACIAS = frozenset(
    {
        "que", "como", "cual", "cuales", "cuando", "donde", "para", "por", "del",
        "las", "los", "una", "uno", "unos", "unas", "con", "sin", "sobre", "the",
        "and", "debe", "deben", "exige", "exigen", "requiere", "requieren", "hay",
        "esta", "este", "esa", "ese", "son", "ser", "mas", "menos", "muy", "todo",
        "toda", "todos", "todas", "documenta", "documentar", "se", "de", "la",
        "el", "en", "un", "y", "o", "a",
    }
)


def normalizar(texto: str) -> str:
    """Minusculas y sin tildes: "metodo" con tilde y sin tilde deben cruzar igual."""
    descompuesto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


def terminos(texto: str) -> set[str]:
    palabras = re.findall(r"[a-z0-9]+", normalizar(texto))
    return {p for p in palabras if len(p) > 2 and p not in _VACIAS}


def puntuar(pregunta: str, entrada: dict[str, Any]) -> int:
    consulta = terminos(pregunta)
    candidatos = terminos(
        f"{entrada.get('pregunta', '')} {entrada.get('etiquetas', '')}"
    )
    return len(consulta & candidatos)


def buscar_en_corpus(
    pregunta: str, entradas: list[dict[str, Any]]
) -> dict[str, Any]:
    """Devuelve la mejor coincidencia del corpus, o el registro de no hallazgo."""
    mejor: dict[str, Any] | None = None
    mejor_puntaje = 0
    for entrada in entradas:
        puntaje = puntuar(pregunta, entrada)
        if puntaje > mejor_puntaje:
            mejor, mejor_puntaje = entrada, puntaje

    if mejor is None or mejor_puntaje < UMBRAL:
        return {
            "pregunta": pregunta,
            "respuesta": SIN_COINCIDENCIA,
            "cita": "",
            "url": "",
            "encontrada": False,
        }

    return {
        "pregunta": pregunta,
        "respuesta": mejor["respuesta"],
        "cita": mejor["cita"],
        "url": mejor.get("url", "") or "",
        "encontrada": True,
    }


__all__ = ["SIN_COINCIDENCIA", "buscar_en_corpus", "normalizar", "puntuar", "terminos"]
