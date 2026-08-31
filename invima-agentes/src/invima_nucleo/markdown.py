"""Lectura determinista de fixtures en Markdown.

Compartida por los agentes que leen dossieres en Markdown: indice de paginas por
marca `<!-- pagina: N -->`, secciones por encabezado y tablas por firma de
columnas. Nada de esto interpreta el contenido -- solo lo ubica, para que cada
valor pueda viajar con el folio del que salio.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Sequence

_MARCA_PAGINA = re.compile(r"<!--\s*pagina:\s*(\d+)\s*-->")
_ENCABEZADO = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_SEPARADOR_TABLA = re.compile(r"^\|[\s\-|:]+\|$")
_VACIOS = {"", "-", "n/a", "na", "null", "no aplica", "no suministrado"}


def celdas(linea: str) -> list[str]:
    return [c.strip() for c in linea.strip().strip("|").split("|")]


def es_vacio(texto: str) -> bool:
    return texto.strip().lower() in _VACIOS


def a_decimal(texto: str) -> Decimal | None:
    try:
        return Decimal(texto.strip().replace(",", ""))
    except (InvalidOperation, ValueError):
        return None


class Documento:
    """Markdown con indice de paginas y secciones, para poder citar el folio."""

    def __init__(self, markdown: str, nombre: str) -> None:
        self.markdown = markdown
        self.nombre = nombre
        self._paginas = [
            (m.start(), int(m.group(1))) for m in _MARCA_PAGINA.finditer(markdown)
        ]
        encabezados = [(m.start(), m.group(1)) for m in _ENCABEZADO.finditer(markdown)]
        self.secciones: list[tuple[str, int, str]] = []
        for indice, (inicio, titulo) in enumerate(encabezados):
            fin = encabezados[indice + 1][0] if indice + 1 < len(encabezados) else len(markdown)
            self.secciones.append((titulo, inicio, markdown[inicio:fin]))

    def pagina_en(self, posicion: int) -> int:
        pagina = 0
        for inicio, numero in self._paginas:
            if inicio <= posicion:
                pagina = numero
            else:
                break
        return pagina

    def seccion(self, fragmento_titulo: str) -> tuple[str, int, str] | None:
        for titulo, inicio, cuerpo in self.secciones:
            if fragmento_titulo.lower() in titulo.lower():
                return titulo, inicio, cuerpo
        return None


def tablas(cuerpo: str) -> list[tuple[list[str], list[list[str]]]]:
    """Extrae los bloques de tabla de una seccion, sin la fila separadora."""
    tablas: list[tuple[list[str], list[list[str]]]] = []
    encabezado: list[str] | None = None
    filas: list[list[str]] = []
    for linea in cuerpo.splitlines():
        limpia = linea.strip()
        if limpia.startswith("|"):
            if _SEPARADOR_TABLA.match(limpia):
                continue
            if encabezado is None:
                encabezado = celdas(limpia)
            else:
                filas.append(celdas(limpia))
            continue
        if encabezado is not None:
            tablas.append((encabezado, filas))
            encabezado, filas = None, []
    if encabezado is not None:
        tablas.append((encabezado, filas))
    return tablas


def tabla_con(
    cuerpo: str, columnas_esperadas: Sequence[str]
) -> tuple[list[str], list[list[str]]] | None:
    esperadas = [c.lower() for c in columnas_esperadas]
    for encabezado, filas in tablas(cuerpo):
        actuales = [c.lower() for c in encabezado]
        if all(col in actuales for col in esperadas):
            return encabezado, filas
    return None




__all__ = ["Documento", "celdas", "es_vacio", "a_decimal", "tablas", "tabla_con"]
