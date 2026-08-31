"""Puerto de consulta a agencias sanitarias de referencia."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RespuestaAgencia:
    agencia: str
    encontrada: bool
    fecha_aprobacion: date | None
    indicacion_aprobada: str | None
    url_fuente: str
    nombre_comercial: str | None = None
    observaciones: str = ""


class AgenciaReferenciaPort(Protocol):
    @property
    def nombre(self) -> str: ...

    def consultar(self, principio_activo: str) -> RespuestaAgencia:
        """Busca el estatus de aprobacion de la molecula. No lanza en caso de
        no encontrarla: devuelve `encontrada=False`, que es informacion util."""
        ...
