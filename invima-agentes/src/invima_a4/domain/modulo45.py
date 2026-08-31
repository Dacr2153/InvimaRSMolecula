"""Agregado de la evidencia cientifica que el A4 audita (Modulos 4, 5 y 7).

Un objeto por bloque del CTD, mas el plan de gestion de riesgos, que no es
evidencia sino la promesa del solicitante sobre como va a vigilar lo que la
evidencia mostro. Se guarda aqui porque el cruce contra las senales del informe
periodico es una de las verificaciones centrales del agente.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .modelos import Especificacion
from .servicios.cruce_toxico_clinico import PlanGestionRiesgos
from .servicios.ensayo_pivotal import EnsayoPivotal
from .servicios.farmacovigilancia import InformePBRER
from .servicios.inmunogenicidad import Inmunogenicidad
from .servicios.preclinico import (
    EstudioFarmacocinetico,
    EstudioReproductivo,
    EstudioToxicologia,
)
from .valores import Dato


@dataclass(frozen=True, slots=True)
class ExpedienteEvidencia:
    radicado: str
    producto: Dato[str]
    farmacocinetica: EstudioFarmacocinetico | None = None
    toxicologia: tuple[EstudioToxicologia, ...] = field(default_factory=tuple)
    reproductiva: EstudioReproductivo | None = None
    ensayo_pivotal: EnsayoPivotal | None = None
    inmunogenicidad: Inmunogenicidad | None = None
    pbrer: InformePBRER | None = None
    plan_riesgos: PlanGestionRiesgos | None = None
    especificaciones_declaradas: Mapping[str, Especificacion] = field(
        default_factory=dict
    )
    textos_libres: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    def a_dict(self) -> dict[str, Any]:
        return {
            "radicado": self.radicado,
            "producto": self.producto.a_dict(),
            "especificaciones_declaradas": {
                nombre: espec.a_dict()
                for nombre, espec in self.especificaciones_declaradas.items()
            },
        }
