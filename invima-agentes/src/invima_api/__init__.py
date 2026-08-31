"""API HTTP del sistema de radicacion y evaluacion.

Capa de entrada sobre los agentes. No contiene reglas de negocio: traduce HTTP a
casos de uso y consulta las tablas de radicacion y evaluacion. Ninguna respuesta
de esta API emite un concepto tecnico; el unico sentido de decision que existe lo
escribe una persona por POST /api/expedientes/{radicado}/decision.
"""

__all__: list[str] = []
