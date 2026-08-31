"""Objetos de valor del dominio.

La pieza central es Dato[T]: ningun valor viaja desnudo por el sistema. Todo campo
declara de donde salio y como se puede verificar. Esto convierte la "separacion
epistemologica" que exigen las reglas en una garantia del tipo, no en una convencion.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from .errores import DatoNoDisponibleError


class OrigenDato(StrEnum):
    """De donde proviene un dato. El evaluador debe poder distinguirlos siempre."""

    EXTRAIDO = "EXTRAIDO"
    """Leido literalmente de un documento del expediente."""

    BUSQUEDA = "BUSQUEDA"
    """Recuperado de una fuente publica externa (OpenFDA, EMA, ClinicalTrials.gov)."""

    RECOMENDACION = "RECOMENDACION"
    """Producido por logica del agente. Nunca es una decision, solo una sugerencia."""

    NO_SUMINISTRADO = "NO_SUMINISTRADO"
    """El campo se busco y no aparece en el expediente. No se infiere ni se deduce."""


@dataclass(frozen=True, slots=True)
class Traza:
    """Ubicacion verificable de un dato.

    Para datos extraidos apunta al folio del expediente; para datos de busqueda,
    a la URL publica consultada. En ambos casos el evaluador puede ir a comprobarlo.
    """

    descripcion: str
    modulo: str | None = None
    seccion: str | None = None
    pagina: int | None = None
    campo: str | None = None
    url: str | None = None

    @classmethod
    def en_documento(
        cls, modulo: str, seccion: str, pagina: int | None, campo: str
    ) -> Traza:
        # Cuando el parser no logro ubicar la pagina se dice, no se inventa un cero.
        ubicacion = f"Pagina {pagina}" if pagina else "Pagina no determinada"
        return cls(
            descripcion=f"{modulo} > {seccion} > {ubicacion} > Campo {campo}",
            modulo=modulo,
            seccion=seccion,
            pagina=pagina,
            campo=campo,
        )

    @classmethod
    def en_fuente_publica(cls, nombre: str, url: str) -> Traza:
        return cls(descripcion=f"{nombre} ({url})", url=url)

    def a_dict(self) -> dict[str, Any]:
        return {
            "descripcion": self.descripcion,
            "modulo": self.modulo,
            "seccion": self.seccion,
            "pagina": self.pagina,
            "campo": self.campo,
            "url": self.url,
        }


@dataclass(frozen=True, slots=True)
class Dinero:
    """Valor monetario en pesos colombianos. Decimal para no perder centavos."""

    monto: Decimal
    moneda: str = "COP"

    @classmethod
    def cop(cls, monto: str | int | float | Decimal) -> Dinero:
        return cls(monto=Decimal(str(monto)))

    def __str__(self) -> str:
        return f"${self.monto:,.2f} {self.moneda}"


def _serializable(valor: Any) -> Any:
    """Reduce un valor de dominio a algo que json.dumps entienda."""
    if valor is None or isinstance(valor, (str, int, bool)):
        return valor
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, float):
        return valor
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()
    if isinstance(valor, Dinero):
        return {"monto": float(valor.monto), "moneda": valor.moneda}
    return str(valor)


@dataclass(frozen=True, slots=True)
class Dato[T]:
    """Un valor acompanado de su procedencia.

    No existe forma de meter un valor al payload de salida sin declarar su origen.
    """

    valor: T | None
    origen: OrigenDato
    traza: Traza | None = None

    @classmethod
    def extraido(cls, valor: T, traza: Traza) -> Dato[T]:
        return cls(valor=valor, origen=OrigenDato.EXTRAIDO, traza=traza)

    @classmethod
    def de_busqueda(cls, valor: T, traza: Traza) -> Dato[T]:
        return cls(valor=valor, origen=OrigenDato.BUSQUEDA, traza=traza)

    @classmethod
    def recomendado(cls, valor: T, razon: str) -> Dato[T]:
        return cls(
            valor=valor,
            origen=OrigenDato.RECOMENDACION,
            traza=Traza(descripcion=f"Recomendacion del agente: {razon}"),
        )

    @classmethod
    def ausente(cls, campo_buscado: str) -> Dato[T]:
        """El campo no aparece en el expediente. Regla dura: no inferir, no asumir."""
        return cls(
            valor=None,
            origen=OrigenDato.NO_SUMINISTRADO,
            traza=Traza(descripcion=f"No suministrado en el expediente: {campo_buscado}"),
        )

    @property
    def presente(self) -> bool:
        return self.valor is not None

    def exigir(self) -> T:
        """Devuelve el valor o falla. Usar solo donde el flujo ya garantizo presencia."""
        if self.valor is None:
            detalle = self.traza.descripcion if self.traza else "sin traza"
            raise DatoNoDisponibleError(detalle)
        return self.valor

    def a_dict(self) -> dict[str, Any]:
        return {
            "valor": _serializable(self.valor),
            "origen": str(self.origen),
            "trazabilidad": self.traza.a_dict() if self.traza else None,
        }


