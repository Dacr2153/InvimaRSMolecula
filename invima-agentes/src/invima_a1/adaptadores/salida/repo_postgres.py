"""Persistencia del expediente en PostgreSQL.

Mismo puerto que RepositorioSQLite (RepositorioExpedientePort) y misma semantica:
`guardar` hace upsert por radicado y `cargar` reconstruye el agregado completo,
eventos incluidos. El adaptador SQLite se conserva para la CLI offline; este es
el que usa la API.

Dos campos que el SQLite no tiene, porque solo existen cuando hay un wizard
detras: `solicitud_id` (la solicitud que dio origen al expediente) y
`carpeta_dossier` (donde quedaron los folios que se evaluaron). Se pasan por
constructor o por `asociar_solicitud`, y nunca se borran en un upsert posterior:
un guardado que no los trae conserva los que ya estaban.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractContextManager, contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from ...domain.auditoria import EventoAuditoria, TipoEvento
from ...domain.estados import DecisionHumana, EstadoExpediente, SentidoDecision
from ...domain.modelos import Expediente

#: Una fabrica de conexiones: cualquier cosa que al llamarse devuelva un context
#: manager con una conexion psycopg. `ConnectionPool.connection` lo cumple.
FabricaConexiones = Callable[[], AbstractContextManager[psycopg.Connection]]


def conexiones_desde_dsn(dsn: str) -> FabricaConexiones:
    """Fabrica de conexiones sueltas. Util para scripts y para la CLI."""

    @contextmanager
    def abrir():  # type: ignore[no-untyped-def]
        with psycopg.connect(dsn, row_factory=dict_row) as conexion:
            yield conexion

    return abrir


def _serializar_decision(decision: DecisionHumana | None) -> Jsonb | None:
    if decision is None:
        return None
    return Jsonb(
        {
            "usuario": decision.usuario,
            "sentido": str(decision.sentido),
            "momento": decision.momento.isoformat(),
            "observaciones": decision.observaciones,
            "campos_corregidos": list(decision.campos_corregidos),
        }
    )


def _leer_decision(crudo: Any) -> DecisionHumana | None:
    if not crudo:
        return None
    if isinstance(crudo, str):
        crudo = json.loads(crudo)
    return DecisionHumana(
        usuario=crudo["usuario"],
        sentido=SentidoDecision(crudo["sentido"]),
        momento=datetime.fromisoformat(crudo["momento"]),
        observaciones=crudo.get("observaciones", ""),
        campos_corregidos=tuple(crudo.get("campos_corregidos", ())),
    )


def _leer_eventos(crudo: Any) -> list[EventoAuditoria]:
    if isinstance(crudo, str):
        crudo = json.loads(crudo)
    return [
        EventoAuditoria(
            momento=datetime.fromisoformat(e["timestamp"]),
            tipo=TipoEvento(e["tipo"]),
            radicado=e["radicado"],
            accion=e["accion"],
            resultado=e["resultado"],
            actor=e.get("actor", "SISTEMA"),
            detalles=e.get("detalles", {}),
        )
        for e in (crudo or [])
    ]


class RepositorioPostgres:
    """Implementa RepositorioExpedientePort sobre la tabla `expedientes`."""

    def __init__(
        self,
        conexiones: FabricaConexiones,
        solicitud_id: UUID | str | None = None,
        carpeta_dossier: Path | str = "",
    ) -> None:
        self._conexiones = conexiones
        self._solicitud_id = str(solicitud_id) if solicitud_id else None
        self._carpeta_dossier = str(carpeta_dossier or "")

    def asociar_solicitud(
        self, solicitud_id: UUID | str | None, carpeta_dossier: Path | str = ""
    ) -> None:
        """Amarra los proximos guardados a una solicitud y a su carpeta de folios."""
        self._solicitud_id = str(solicitud_id) if solicitud_id else None
        self._carpeta_dossier = str(carpeta_dossier or "")

    def guardar(self, expediente: Expediente, payload: dict[str, Any]) -> None:
        with self._conexiones() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO expedientes
                        (radicado, solicitud_id, fecha_radicacion, estado,
                         decision_humana, eventos, payload, carpeta_dossier,
                         actualizado_en)
                    VALUES (%(radicado)s, %(solicitud_id)s, %(fecha)s, %(estado)s,
                            %(decision)s, %(eventos)s, %(payload)s, %(carpeta)s, now())
                    ON CONFLICT (radicado) DO UPDATE SET
                        estado          = EXCLUDED.estado,
                        decision_humana = EXCLUDED.decision_humana,
                        eventos         = EXCLUDED.eventos,
                        payload         = EXCLUDED.payload,
                        solicitud_id    = COALESCE(EXCLUDED.solicitud_id,
                                                   expedientes.solicitud_id),
                        carpeta_dossier = CASE
                            WHEN EXCLUDED.carpeta_dossier <> '' THEN EXCLUDED.carpeta_dossier
                            ELSE expedientes.carpeta_dossier
                        END,
                        actualizado_en  = now()
                    """,
                    {
                        "radicado": expediente.radicado,
                        "solicitud_id": self._solicitud_id,
                        "fecha": expediente.fecha_radicacion,
                        "estado": str(expediente.estado),
                        "decision": _serializar_decision(expediente.decision_humana),
                        "eventos": Jsonb([e.a_dict() for e in expediente.eventos]),
                        "payload": Jsonb(payload),
                        "carpeta": self._carpeta_dossier,
                    },
                )
            conexion.commit()

    def cargar(self, radicado: str) -> tuple[Expediente, dict[str, Any]] | None:
        with self._conexiones() as conexion:
            with conexion.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT radicado, fecha_radicacion, estado, decision_humana,
                           eventos, payload
                      FROM expedientes
                     WHERE radicado = %s
                    """,
                    (radicado,),
                )
                fila = cursor.fetchone()

        if fila is None:
            return None

        fecha = fila["fecha_radicacion"]
        if isinstance(fecha, str):
            fecha = date.fromisoformat(fecha)

        expediente = Expediente(
            radicado=fila["radicado"],
            fecha_radicacion=fecha,
            estado=EstadoExpediente(fila["estado"]),
            decision_humana=_leer_decision(fila["decision_humana"]),
            eventos=_leer_eventos(fila["eventos"]),
        )
        payload = fila["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        return expediente, payload or {}


__all__ = ["RepositorioPostgres", "FabricaConexiones", "conexiones_desde_dsn"]
