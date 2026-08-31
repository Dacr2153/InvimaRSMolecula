"""Puerto de persistencia del expediente."""

from __future__ import annotations

from typing import Any, Protocol

from ..domain.modelos import Expediente


class RepositorioExpedientePort(Protocol):
    def guardar(self, expediente: Expediente, payload: dict[str, Any]) -> None: ...

    def cargar(self, radicado: str) -> tuple[Expediente, dict[str, Any]] | None: ...
