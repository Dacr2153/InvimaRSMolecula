"""Log de auditoria append-only en JSONL.

Una linea por evento. No hay metodo para editar ni para borrar: el puerto no lo
expone y esta implementacion abre el archivo siempre en modo append. Requisito
7.2 de las reglas de la Hackaton.
"""

from __future__ import annotations

import json
from pathlib import Path

from ...domain.auditoria import EventoAuditoria, TipoEvento
from datetime import datetime


class AuditLogJSONL:
    def __init__(self, ruta: Path) -> None:
        self._ruta = ruta
        self._ruta.parent.mkdir(parents=True, exist_ok=True)

    def registrar(self, evento: EventoAuditoria) -> None:
        with self._ruta.open("a", encoding="utf-8") as archivo:
            archivo.write(json.dumps(evento.a_dict(), ensure_ascii=False) + "\n")

    def eventos_de(self, radicado: str) -> tuple[EventoAuditoria, ...]:
        if not self._ruta.exists():
            return ()
        eventos: list[EventoAuditoria] = []
        with self._ruta.open(encoding="utf-8") as archivo:
            for linea in archivo:
                if not linea.strip():
                    continue
                datos = json.loads(linea)
                if datos.get("radicado") != radicado:
                    continue
                eventos.append(
                    EventoAuditoria(
                        momento=datetime.fromisoformat(datos["timestamp"]),
                        tipo=TipoEvento(datos["tipo"]),
                        radicado=datos["radicado"],
                        accion=datos["accion"],
                        resultado=datos["resultado"],
                        actor=datos.get("actor", "SISTEMA"),
                        detalles=datos.get("detalles", {}),
                    )
                )
        return tuple(eventos)


class AuditLogMemoria:
    """Implementacion en memoria para pruebas."""

    def __init__(self) -> None:
        self.eventos: list[EventoAuditoria] = []

    def registrar(self, evento: EventoAuditoria) -> None:
        self.eventos.append(evento)

    def eventos_de(self, radicado: str) -> tuple[EventoAuditoria, ...]:
        return tuple(e for e in self.eventos if e.radicado == radicado)
