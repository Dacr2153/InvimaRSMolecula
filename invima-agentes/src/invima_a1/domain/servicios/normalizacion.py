"""Normalizacion de denominaciones comunes internacionales (DCI/INN).

Comparar principios activos por igualdad de cadena falla por razones triviales:
tildes, mayusculas, y sobre todo las sales e hidratos que acompanan al principio
activo en la etiqueta pero no cambian su identidad regulatoria.
"""

from __future__ import annotations

import re
import unicodedata

#: Sufijos de sal, ester e hidrato que no alteran la identidad del principio activo.
#: Se incluyen las formas en ingles porque las agencias de referencia etiquetan asi
#: (openFDA devuelve "METFORMIN HYDROCHLORIDE", no "clorhidrato de metformina").
SUFIJOS_SAL: tuple[str, ...] = (
    "clorhidrato",
    "hidrocloruro",
    "bromhidrato",
    "sulfato",
    "fosfato",
    "maleato",
    "tartrato",
    "citrato",
    "acetato",
    "besilato",
    "mesilato",
    "succinato",
    "fumarato",
    "sodico",
    "sodica",
    "potasico",
    "potasica",
    "calcico",
    "calcica",
    "monohidrato",
    "dihidrato",
    "trihidrato",
    "anhidro",
    "anhidra",
    # Formas en ingles, tal como aparecen en las etiquetas de FDA y MHRA
    "hydrochloride",
    "hydrobromide",
    "sulfate",
    "phosphate",
    "maleate",
    "tartrate",
    "citrate",
    "acetate",
    "besylate",
    "mesylate",
    "succinate",
    "fumarate",
    "sodium",
    "potassium",
    "calcium",
    "monohydrate",
    "dihydrate",
    "trihydrate",
    "anhydrous",
)

#: Correspondencias de terminacion entre la DCI en espanol y el INN en ingles.
#: El INN es el mismo principio activo con ortografia adaptada a cada idioma:
#: "metformina" (es) es "metformin" (en). Sin esto, el reliance no encuentra
#: en FDA ni en MHRA ninguna molecula escrita como llega en el dossier colombiano.
#: Orden importante: la primera terminacion que coincide es la que se aplica.
TERMINACIONES_INN: tuple[tuple[str, str], ...] = (
    ("azol", "azole"),
    ("ina", "in"),
    ("ano", "ane"),
    ("eno", "ene"),
    ("ida", "ide"),
    ("ona", "one"),
    ("ico", "ic"),
)

_CONECTORES = ("de", "del", "la", "el")


def sin_tildes(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


def normalizar_dci(nombre: str) -> str:
    """Reduce un nombre de principio activo a su forma canonica comparable.

    >>> normalizar_dci("Clorhidrato de Metformina")
    'metformina'
    >>> normalizar_dci("METFORMINA HCl")
    'metformina'
    """
    texto = sin_tildes(nombre).lower()
    texto = texto.replace("hcl", " ")
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)
    tokens = [t for t in texto.split() if t]
    tokens = [
        t for t in tokens if t not in SUFIJOS_SAL and t not in _CONECTORES
    ]
    return " ".join(tokens).strip()


def variantes_inn(nombre: str) -> tuple[str, ...]:
    """Formas equivalentes de una DCI para buscarla en agencias de habla inglesa.

    Devuelve siempre la forma normalizada original primero; despues, si alguna
    terminacion aplica, la variante inglesa.

    >>> variantes_inn("Clorhidrato de Metformina")
    ('metformina', 'metformin')
    >>> variantes_inn("bosentan")
    ('bosentan',)
    """
    base = normalizar_dci(nombre)
    if not base:
        return ()

    formas = [base]
    palabras = base.split()
    for es, en in TERMINACIONES_INN:
        if palabras[-1].endswith(es) and len(palabras[-1]) > len(es) + 2:
            variante = " ".join(palabras[:-1] + [palabras[-1][: -len(es)] + en])
            if variante not in formas:
                formas.append(variante)
            break
    return tuple(formas)


def coinciden_dci(a: str, b: str) -> bool:
    """Igualdad de principio activo, tolerante a sales, tildes e idioma del INN."""
    if not a or not b:
        return False
    return bool(set(variantes_inn(a)) & set(variantes_inn(b)))
