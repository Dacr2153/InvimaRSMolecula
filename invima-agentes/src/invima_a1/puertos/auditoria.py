"""Puerto del log de auditoria. Append-only por contrato."""

from __future__ import annotations

from typing import Protocol

from ..domain.auditoria import EventoAuditoria


class AuditLogPort(Protocol):
    def registrar(self, evento: EventoAuditoria) -> None:
        """Anexa un evento. Ninguna implementacion puede editar ni borrar."""
        ...

    def eventos_de(self, radicado: str) -> tuple[EventoAuditoria, ...]: ...
