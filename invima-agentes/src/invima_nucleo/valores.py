"""Primitivas de trazabilidad del sistema.

Ningun agente redefine Dato ni Traza: todos reusan las del A1 para que un
valor de calidad o de evidencia viaje con la misma garantia de procedencia
que un dato de radicacion.
Si algun dia el nucleo se extrae a un paquete comun, solo cambia este archivo.
"""

from invima_a1.domain.valores import Dato, Dinero, OrigenDato, Traza

__all__ = ["Dato", "Dinero", "OrigenDato", "Traza"]
