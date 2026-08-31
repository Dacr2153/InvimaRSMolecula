"""Alertas del A2: severidad, consolidacion y efecto sobre el tramite.

Una alerta no es una decision. Dice que se comparo, que se esperaba, que se
encontro y donde verificarlo. Quien concluye si eso invalida el tramite es el
evaluador.

La severidad si tiene efecto tecnico, y uno solo: una alerta CRITICA impide que
el A2 recomiende repartir el expediente a los grupos evaluadores. No lo rechaza
ni lo devuelve, porque eso seria decidir. Lo retiene y lo pone a la vista.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum

from ..valores import Traza


class Severidad(IntEnum):
    """Orden de gravedad. Es IntEnum para poder tomar el maximo de un conjunto."""

    INFORMATIVA = 0
    MEDIA = 1
    ALTA = 2
    CRITICA = 3

    def __str__(self) -> str:
        return self.name


class TipoAlerta(StrEnum):
    PODER_SIN_APOSTILLA = "PODER_SIN_APOSTILLA"
    PODER_SIN_TRADUCTOR = "PODER_SIN_TRADUCTOR"
    CCB_VENCIDA = "CCB_VENCIDA"
    BPM_VENCIDA = "BPM_VENCIDA"
    BPM_INCOHERENTE = "BPM_INCOHERENTE"
    BPM_ROL_FALTANTE = "BPM_ROL_FALTANTE"
    NIT_INCOHERENTE = "NIT_INCOHERENTE"
    RAZON_SOCIAL_INCOHERENTE = "RAZON_SOCIAL_INCOHERENTE"
    DOCUMENTO_FALTANTE = "DOCUMENTO_FALTANTE"
    CONTENIDO_SOSPECHOSO = "CONTENIDO_SOSPECHOSO"
    CLASIFICACION_INDETERMINADA = "CLASIFICACION_INDETERMINADA"


@dataclass(frozen=True, slots=True)
class Alerta:
    """Un hallazgo concreto, con lo comparado a la vista."""

    tipo: TipoAlerta
    severidad: Severidad
    mensaje: str
    esperado: str = ""
    encontrado: str = ""
    traza: Traza | None = None

    def a_dict(self) -> dict[str, object]:
        return {
            "tipo": str(self.tipo),
            "severidad": str(self.severidad),
            "mensaje": self.mensaje,
            "esperado": self.esperado,
            "encontrado": self.encontrado,
            "trazabilidad": self.traza.a_dict() if self.traza else None,
        }


def severidad_maxima(alertas: tuple[Alerta, ...]) -> Severidad:
    """Gravedad del conjunto. Sin alertas, INFORMATIVA."""
    if not alertas:
        return Severidad.INFORMATIVA
    return max(a.severidad for a in alertas)


def hay_bloqueo(alertas: tuple[Alerta, ...]) -> bool:
    """Si alguna alerta es CRITICA, el expediente no se recomienda para reparto."""
    return severidad_maxima(alertas) is Severidad.CRITICA


def ordenar(alertas: tuple[Alerta, ...]) -> tuple[Alerta, ...]:
    """Las mas graves primero; a igual severidad, orden estable de deteccion."""
    return tuple(
        sorted(alertas, key=lambda a: -int(a.severidad))
    )
