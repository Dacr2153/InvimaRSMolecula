"""Primitivas de trazabilidad del sistema.

El A2 no redefine Dato ni Traza: reusa las del nucleo para que una verificacion
legal viaje con la misma garantia de procedencia que un dato de radicacion. Que
la apostilla este presente no es un booleano suelto, es un Dato[bool] que apunta
al folio donde se leyo el sello.
"""

from invima_a1.domain.valores import Dato, Dinero, OrigenDato, Traza

__all__ = ["Dato", "Dinero", "OrigenDato", "Traza"]
