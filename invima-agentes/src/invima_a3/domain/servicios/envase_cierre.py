"""Auditoria del sistema envase-cierre (M3.2.R).

Dos verificaciones distintas conviven aqui. Los ensayos de extraibles y
lixiviables se contrastan como cualquier otra medicion. Los cambios de
componente son otra cosa: un cambio sin estudio comparativo no es un desvio
numerico, es un vacio de evidencia, y se reporta como tal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Mapping

from ..modelos import ClaseHallazgo, Especificacion, Hallazgo, Medicion, Severidad
from ..valores import Dato
from .contraste import ParametroAuditado, auditar, campo_ausente, respaldo_documental

ETIQUETAS = ("envase_cierre", "M3.2.R")


@dataclass(frozen=True, slots=True)
class Componente:
    """Una pieza del sistema envase-cierre y el material que declara."""

    nombre: str
    material: Dato[str]
    norma_referencia: Dato[str] | None = None

    def a_dict(self) -> dict[str, Any]:
        return {
            "componente": self.nombre,
            "material": self.material.a_dict(),
            "norma_referencia": (
                self.norma_referencia.a_dict() if self.norma_referencia else None
            ),
        }


@dataclass(frozen=True, slots=True)
class CambioComponente:
    """Sustitucion de un componente respecto de lo previamente registrado."""

    componente: str
    material_previo: Dato[str]
    material_nuevo: Dato[str]
    fecha_efectiva: Dato[date] | None = None
    estudio_comparativo: Dato[str] | None = None

    def a_dict(self) -> dict[str, Any]:
        return {
            "componente": self.componente,
            "material_previo": self.material_previo.a_dict(),
            "material_nuevo": self.material_nuevo.a_dict(),
            "fecha_efectiva": (
                self.fecha_efectiva.a_dict() if self.fecha_efectiva else None
            ),
            "estudio_comparativo": (
                self.estudio_comparativo.a_dict() if self.estudio_comparativo else None
            ),
        }


@dataclass(frozen=True, slots=True)
class SistemaEnvaseCierre:
    componentes: tuple[Componente, ...] = field(default_factory=tuple)
    ensayos: tuple[Medicion, ...] = field(default_factory=tuple)
    cambios: tuple[CambioComponente, ...] = field(default_factory=tuple)

    def a_dict(self) -> dict[str, Any]:
        return {
            "componentes": [c.a_dict() for c in self.componentes],
            "ensayos": [m.a_dict() for m in self.ensayos],
            "cambios": [c.a_dict() for c in self.cambios],
        }


@dataclass(frozen=True, slots=True)
class ReporteEnvaseCierre:
    sistema: SistemaEnvaseCierre
    hallazgos: tuple[Hallazgo, ...]

    def a_dict(self) -> dict[str, Any]:
        return {
            "envase_cierre": self.sistema.a_dict(),
            "hallazgos": [h.a_dict() for h in self.hallazgos],
        }


def auditar_envase_cierre(
    sistema: SistemaEnvaseCierre,
    especificaciones: Mapping[str, Especificacion],
) -> ReporteEnvaseCierre:
    hallazgos: list[Hallazgo] = []

    for componente in sistema.componentes:
        faltante = campo_ausente(
            f"Material del componente '{componente.nombre}'",
            componente.material,
            ETIQUETAS,
        )
        if faltante is not None:
            hallazgos.append(faltante)

    hallazgos.extend(
        auditar(
            [
                ParametroAuditado(
                    medicion=m,
                    especificacion=especificaciones.get(m.parametro),
                    severidad_si_desvia=Severidad.ALTA,
                )
                for m in sistema.ensayos
            ],
            etiquetas=ETIQUETAS,
        )
    )

    for cambio in sistema.cambios:
        sin_comparativo = respaldo_documental(
            parametro=f"Cambio de componente '{cambio.componente}'",
            referencia=cambio.estudio_comparativo,
            descripcion_esperada=(
                f"el estudio comparativo entre el material previo "
                f"({cambio.material_previo.valor or 'no declarado'}) y el nuevo "
                f"({cambio.material_nuevo.valor or 'no declarado'})"
            ),
            etiquetas=ETIQUETAS + ("cambio_componente",),
            severidad=Severidad.ALTA,
        )
        if sin_comparativo is not None:
            hallazgos.append(sin_comparativo)
        if cambio.fecha_efectiva is None or not cambio.fecha_efectiva.presente:
            hallazgos.append(
                Hallazgo(
                    parametro=f"Fecha efectiva del cambio en '{cambio.componente}'",
                    clase=ClaseHallazgo.RESULTADO_NO_SUMINISTRADO,
                    severidad=Severidad.MEDIA,
                    observacion=(
                        f"El expediente declara un cambio de material en "
                        f"'{cambio.componente}' sin fecha efectiva. Sin fecha no se "
                        f"puede saber que lotes se fabricaron con cada material."
                    ),
                    etiquetas=ETIQUETAS + ("cambio_componente",),
                )
            )

    return ReporteEnvaseCierre(sistema=sistema, hallazgos=tuple(hallazgos))
