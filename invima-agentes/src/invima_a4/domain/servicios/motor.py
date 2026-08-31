"""Consolidacion de hallazgos y guardia lexica. Definidas en el nucleo.

La guardia lexica pesa igual sobre el A4 que sobre el A3, y en el A4 pesa mas:
es el agente al que mas cerca le queda la tentacion de concluir.
"""

from invima_nucleo.hallazgos import (
    LEXICO_PROHIBIDO,
    ResumenAuditoria,
    auditar_lexico,
    consolidar,
    ordenar,
    terminos_decisorios,
)

__all__ = [
    "LEXICO_PROHIBIDO",
    "ResumenAuditoria",
    "auditar_lexico",
    "consolidar",
    "ordenar",
    "terminos_decisorios",
]
