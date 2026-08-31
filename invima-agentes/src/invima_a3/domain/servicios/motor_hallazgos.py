"""Consolidacion de hallazgos y guardia lexica. Definidas en el nucleo.

La guardia lexica es del sistema, no del A3: la prohibicion del art. 7.1 pesa
igual sobre la salida de cada agente.
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
