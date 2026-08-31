"""Log de auditoria append-only sobre PostgreSQL.

Equivalente en base de datos de AuditLogJSONL. La inmutabilidad no depende de
esta clase: la tabla `eventos_auditoria` tiene un trigger que rechaza UPDATE y
DELETE aunque el intento venga por psql con el rol dueno. Aqui solo se anexa.
"""

from __future__ import annotations

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from ...domain.auditoria import EventoAuditoria, TipoEvento
from .repo_postgres import FabricaConexiones


class AuditLogPostgres:
    """Implementa AuditLogPort. No expone forma de editar ni de borrar."""

    def __init__(self, conexiones: FabricaConexiones) -> None:
        self._conexiones = conexiones

    def registrar(self, evento: EventoAuditoria) -> None:
        with self._conexiones() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO eventos_auditoria
                        (momento, radicado, tipo, accion, resultado, actor, detalles)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        evento.momento,
                        evento.radicado,
                        str(evento.tipo),
                        evento.accion,
                        evento.resultado,
                        evento.actor,
                        Jsonb(evento.detalles or {}),
                    ),
                )
            conexion.commit()

    def eventos_de(self, radicado: str) -> tuple[EventoAuditoria, ...]:
        with self._conexiones() as conexion:
            with conexion.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT momento, radicado, tipo, accion, resultado, actor, detalles
                      FROM eventos_auditoria
                     WHERE radicado = %s
                     ORDER BY momento, id
                    """,
                    (radicado,),
                )
                filas = cursor.fetchall()

        return tuple(
            EventoAuditoria(
                momento=fila["momento"],
                tipo=TipoEvento(fila["tipo"]),
                radicado=fila["radicado"],
                accion=fila["accion"],
                resultado=fila["resultado"],
                actor=fila["actor"],
                detalles=fila["detalles"] or {},
            )
            for fila in filas
        )


__all__ = ["AuditLogPostgres"]
