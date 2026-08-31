"""Agregado del Modulo 3 tal como el agente lo lee.

Un objeto por seccion del CTD de calidad, mas el diccionario de especificaciones
que el propio expediente declara. Las especificaciones viven aqui y no dentro de
cada servicio a proposito: son datos del dossier, no constantes del programa.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .modelos import Especificacion
from .servicios.consistencia_lotes import Lote
from .servicios.envase_cierre import SistemaEnvaseCierre
from .servicios.estabilidad import EstudioEstabilidad
from .servicios.inactivacion_viral import ProcesoInactivacionViral
from .servicios.sustancia_activa import SustanciaActiva
from .valores import Dato


@dataclass(frozen=True, slots=True)
class ExpedienteCalidad:
    """Todo lo que el A3 necesita del expediente, ya estructurado y trazado."""

    radicado: str
    producto: Dato[str]
    sustancia_activa: SustanciaActiva
    proceso_viral: ProcesoInactivacionViral
    envase_cierre: SistemaEnvaseCierre
    especificaciones_declaradas: Mapping[str, Especificacion] = field(
        default_factory=dict
    )
    lotes: tuple[Lote, ...] = field(default_factory=tuple)
    estudios_estabilidad: tuple[EstudioEstabilidad, ...] = field(default_factory=tuple)
    textos_libres: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    """Pares (ubicacion, texto) que pasan por el detector de inyeccion."""

    def a_dict(self) -> dict[str, Any]:
        return {
            "radicado": self.radicado,
            "producto": self.producto.a_dict(),
            "especificaciones_declaradas": {
                nombre: espec.a_dict()
                for nombre, espec in self.especificaciones_declaradas.items()
            },
        }
