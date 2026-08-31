"""Persistencia del expediente en SQLite.

SQLite y no PostgreSQL por decision de presupuesto y tiempo: cero servidor, cero
configuracion. Como esta detras de RepositorioExpedientePort, migrar a PostgreSQL
mas adelante es escribir otro adaptador sin tocar el dominio.

El historial de eventos se guarda completo: el expediente debe poder reconstruirse.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

from ...domain.auditoria import EventoAuditoria, TipoEvento
from ...domain.estados import DecisionHumana, EstadoExpediente, SentidoDecision
from ...domain.modelos import Expediente

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS expedientes (
    radicado          TEXT PRIMARY KEY,
    fecha_radicacion  TEXT NOT NULL,
    estado            TEXT NOT NULL,
    decision_humana   TEXT,
    eventos           TEXT NOT NULL,
    payload           TEXT NOT NULL,
    actualizado_en    TEXT NOT NULL
);
"""


class RepositorioSQLite:
    def __init__(self, ruta: Path) -> None:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        self._ruta = ruta
        with self._conectar() as conexion:
            conexion.executescript(_ESQUEMA)

    def _conectar(self) -> sqlite3.Connection:
        conexion = sqlite3.connect(self._ruta)
        conexion.row_factory = sqlite3.Row
        return conexion

    def guardar(self, expediente: Expediente, payload: dict[str, Any]) -> None:
        decision = expediente.decision_humana
        with self._conectar() as conexion:
            conexion.execute(
                """
                INSERT INTO expedientes
                    (radicado, fecha_radicacion, estado, decision_humana,
                     eventos, payload, actualizado_en)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(radicado) DO UPDATE SET
                    estado = excluded.estado,
                    decision_humana = excluded.decision_humana,
                    eventos = excluded.eventos,
                    payload = excluded.payload,
                    actualizado_en = excluded.actualizado_en
                """,
                (
                    expediente.radicado,
                    expediente.fecha_radicacion.isoformat(),
                    str(expediente.estado),
                    (
                        json.dumps(
                            {
                                "usuario": decision.usuario,
                                "sentido": str(decision.sentido),
                                "momento": decision.momento.isoformat(),
                                "observaciones": decision.observaciones,
                                "campos_corregidos": list(decision.campos_corregidos),
                            },
                            ensure_ascii=False,
                        )
                        if decision
                        else None
                    ),
                    json.dumps(
                        [e.a_dict() for e in expediente.eventos], ensure_ascii=False
                    ),
                    json.dumps(payload, ensure_ascii=False),
                    datetime.now().isoformat(),
                ),
            )

    def cargar(self, radicado: str) -> tuple[Expediente, dict[str, Any]] | None:
        with self._conectar() as conexion:
            fila = conexion.execute(
                "SELECT * FROM expedientes WHERE radicado = ?", (radicado,)
            ).fetchone()

        if fila is None:
            return None

        decision = None
        if fila["decision_humana"]:
            crudo = json.loads(fila["decision_humana"])
            decision = DecisionHumana(
                usuario=crudo["usuario"],
                sentido=SentidoDecision(crudo["sentido"]),
                momento=datetime.fromisoformat(crudo["momento"]),
                observaciones=crudo.get("observaciones", ""),
                campos_corregidos=tuple(crudo.get("campos_corregidos", ())),
            )

        expediente = Expediente(
            radicado=fila["radicado"],
            fecha_radicacion=date.fromisoformat(fila["fecha_radicacion"]),
            estado=EstadoExpediente(fila["estado"]),
            decision_humana=decision,
            eventos=[
                EventoAuditoria(
                    momento=datetime.fromisoformat(e["timestamp"]),
                    tipo=TipoEvento(e["tipo"]),
                    radicado=e["radicado"],
                    accion=e["accion"],
                    resultado=e["resultado"],
                    actor=e.get("actor", "SISTEMA"),
                    detalles=e.get("detalles", {}),
                )
                for e in json.loads(fila["eventos"])
            ],
        )
        return expediente, json.loads(fila["payload"])


class RepositorioMemoria:
    """Implementacion en memoria para pruebas."""

    def __init__(self) -> None:
        self._datos: dict[str, tuple[Expediente, dict[str, Any]]] = {}

    def guardar(self, expediente: Expediente, payload: dict[str, Any]) -> None:
        self._datos[expediente.radicado] = (expediente, payload)

    def cargar(self, radicado: str) -> tuple[Expediente, dict[str, Any]] | None:
        return self._datos.get(radicado)
