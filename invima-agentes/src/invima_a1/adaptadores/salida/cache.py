"""Cache en disco para los puertos de consulta externa.

Cada molecula se consulta a cada fuente publica UNA vez. La segunda corrida sale
del disco. Con un presupuesto de cinco dolares esto no es una optimizacion: es
lo que hace viable iterar.

Decorador, no herencia: envuelve cualquier implementacion de los puertos sin que
el dominio ni el caso de uso se enteren.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from datetime import date
from pathlib import Path
from typing import Any

from ...puertos.agencias import AgenciaReferenciaPort, RespuestaAgencia
from ...puertos.ensayos import EnsayosClinicosPort, RespuestaEnsayo


class CacheDisco:
    def __init__(self, directorio: Path) -> None:
        self._dir = directorio
        self._dir.mkdir(parents=True, exist_ok=True)

    def _ruta(self, espacio: str, clave: str) -> Path:
        digest = hashlib.sha256(clave.lower().encode("utf-8")).hexdigest()[:16]
        return self._dir / f"{espacio}__{digest}.json"

    def leer(self, espacio: str, clave: str) -> dict[str, Any] | None:
        ruta = self._ruta(espacio, clave)
        if not ruta.exists():
            return None
        return json.loads(ruta.read_text(encoding="utf-8"))

    def escribir(self, espacio: str, clave: str, valor: Any) -> None:
        datos = asdict(valor) if is_dataclass(valor) else valor
        self._ruta(espacio, clave).write_text(
            json.dumps(datos, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )


def _a_fecha(valor: Any) -> date | None:
    if valor is None:
        return None
    if isinstance(valor, date):
        return valor
    return date.fromisoformat(str(valor))


class AgenciaCacheada:
    """Envuelve un AgenciaReferenciaPort con cache en disco."""

    def __init__(self, interno: AgenciaReferenciaPort, cache: CacheDisco) -> None:
        self._interno = interno
        self._cache = cache

    @property
    def nombre(self) -> str:
        return self._interno.nombre

    def consultar(self, principio_activo: str) -> RespuestaAgencia:
        espacio = f"agencia_{self.nombre.lower().replace(' ', '_')}"
        guardado = self._cache.leer(espacio, principio_activo)
        if guardado is not None:
            guardado["fecha_aprobacion"] = _a_fecha(guardado.get("fecha_aprobacion"))
            return RespuestaAgencia(**guardado)

        respuesta = self._interno.consultar(principio_activo)
        self._cache.escribir(espacio, principio_activo, respuesta)
        return respuesta


class EnsayosCacheados:
    """Envuelve un EnsayosClinicosPort con cache en disco."""

    def __init__(self, interno: EnsayosClinicosPort, cache: CacheDisco) -> None:
        self._interno = interno
        self._cache = cache

    def consultar(self, nct_id: str) -> RespuestaEnsayo:
        guardado = self._cache.leer("ensayos", nct_id)
        if guardado is not None:
            return RespuestaEnsayo(**guardado)
        respuesta = self._interno.consultar(nct_id)
        self._cache.escribir("ensayos", nct_id, respuesta)
        return respuesta
