"""Normalizacion de razones sociales y de NIT.

El spec original del A2 pedia que los nombres de titular, fabricante e importador
coincidieran "byte a byte" entre el formulario y los certificados. Esa regla
produce falsos positivos en masa: la misma empresa aparece como "CellGenix
Biologics S.A.", "CELLGENIX BIOLOGICS SA" y "Cellgenix Biologics, S.A." en tres
documentos emitidos por tres autoridades distintas.

El A1 ya resolvio el mismo problema para principios activos en `normalizacion.py`
(clorhidrato de metformina vs. METFORMINA HCl). Aqui se aplica el mismo criterio a
las personas juridicas: se compara la forma canonica, y cuando la comparacion
falla se muestra el par completo al evaluador en vez de afirmar una identidad que
no consta.
"""

from __future__ import annotations

import re

from invima_a1.domain.servicios.normalizacion import sin_tildes

#: Formas societarias que varian de documento a documento sin cambiar la persona
#: juridica. Se incluyen las extranjeras porque los BPM vienen de otras
#: jurisdicciones: una planta alemana certifica como GmbH y se declara como Ltd.
FORMAS_SOCIETARIAS: frozenset[str] = frozenset(
    {
        "sa", "sas", "sac", "ltda", "limitada", "eu", "sca", "scs",
        "inc", "incorporated", "llc", "lp", "llp", "corp", "corporation",
        "co", "company", "ltd", "plc", "gmbh", "ag", "kg", "bv", "nv",
        "srl", "spa", "sarl", "sas", "ab", "as", "oy", "pte", "pty",
    }
)

_RUIDO = ("y cia", "and co", "grupo", "group")


def normalizar_razon_social(nombre: str) -> str:
    """Reduce una razon social a su forma canonica comparable.

    >>> normalizar_razon_social("CellGenix Biologics, S.A.")
    'cellgenix biologics'
    >>> normalizar_razon_social("CELLGENIX BIOLOGICS SA")
    'cellgenix biologics'
    """
    texto = sin_tildes(nombre).lower()
    # Los puntos de las abreviaturas societarias se eliminan, no se sustituyen por
    # espacio: "S.A." debe quedar como el token "sa" y ser reconocible como forma
    # societaria, no partirse en dos letras sueltas.
    texto = texto.replace(".", "")
    for ruido in _RUIDO:
        texto = texto.replace(ruido, " ")
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)
    tokens = [
        t
        for t in texto.split()
        # Las letras sueltas sobrevivientes ("S. A." con espacio) no aportan
        # identidad; descartarlas evita que el formato decida la comparacion.
        if len(t) > 1 and t not in FORMAS_SOCIETARIAS
    ]
    return " ".join(tokens).strip()


def coinciden_razon_social(a: str | None, b: str | None) -> bool:
    """Identidad de persona juridica, tolerante a forma societaria y puntuacion."""
    if not a or not b:
        return False
    return normalizar_razon_social(a) == normalizar_razon_social(b)


def normalizar_nit(nit: str) -> str:
    """Deja solo los digitos, incluido el de verificacion.

    El NIT colombiano se escribe con puntos y guion en unos documentos y corrido
    en otros. Comparar la cadena tal cual haria fallar el cruce por formato, que
    es justo lo contrario de lo que la verificacion busca detectar.

    >>> normalizar_nit("901.458.789-2")
    '9014587892'
    """
    return re.sub(r"\D", "", nit or "")


def coinciden_nit(a: str | None, b: str | None) -> bool:
    """Identidad de NIT ignorando puntuacion, pero no el digito de verificacion.

    El digito de verificacion se conserva a proposito: dos NIT que difieren solo
    en el son dos contribuyentes distintos, y esa es exactamente la clase de
    suplantacion que la verificacion debe atrapar.
    """
    izq, der = normalizar_nit(a or ""), normalizar_nit(b or "")
    if not izq or not der:
        return False
    return izq == der
