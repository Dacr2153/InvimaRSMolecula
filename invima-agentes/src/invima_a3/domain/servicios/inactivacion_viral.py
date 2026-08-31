"""Auditoria de la validacion de remocion e inactivacion viral (M3.2.S).

El punto ciego que este servicio cubre: un factor de reduccion viral (LRV) es un
numero que solo significa algo junto a tres cosas -- sobre que virus modelo se
midio, en que etapa del proceso, y en que estudio consta. Un LRV suelto no es
un resultado verificable, y el agente lo dice en vez de contrastarlo contra un
limite como si lo fuera.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from ..modelos import ClaseHallazgo, Especificacion, Hallazgo, Medicion, Severidad
from ..valores import Dato
from .contraste import ParametroAuditado, auditar, campo_ausente, respaldo_documental

ETIQUETAS = ("inactivacion_viral", "M3.2.S")


@dataclass(frozen=True, slots=True)
class EtapaReduccionViral:
    """Una etapa del proceso con su factor de reduccion declarado."""

    nombre: str
    lrv: Medicion
    virus_modelo: tuple[Dato[str], ...] = field(default_factory=tuple)

    @property
    def declara_virus_modelo(self) -> bool:
        return any(v.presente for v in self.virus_modelo)

    def a_dict(self) -> dict[str, Any]:
        return {
            "etapa": self.nombre,
            "lrv": self.lrv.a_dict(),
            "virus_modelo": [v.a_dict() for v in self.virus_modelo],
        }


@dataclass(frozen=True, slots=True)
class ProcesoInactivacionViral:
    """Parametros del proceso de depuracion viral, tal como los declara M3.2.S."""

    metodo: Dato[str]
    estudio_referencia: Dato[str]
    parametros_proceso: tuple[Medicion, ...] = field(default_factory=tuple)
    etapas: tuple[EtapaReduccionViral, ...] = field(default_factory=tuple)

    def a_dict(self) -> dict[str, Any]:
        return {
            "metodo": self.metodo.a_dict(),
            "estudio_referencia": self.estudio_referencia.a_dict(),
            "parametros_proceso": [m.a_dict() for m in self.parametros_proceso],
            "etapas": [e.a_dict() for e in self.etapas],
        }


@dataclass(frozen=True, slots=True)
class ReporteInactivacionViral:
    proceso: ProcesoInactivacionViral
    hallazgos: tuple[Hallazgo, ...]

    def a_dict(self) -> dict[str, Any]:
        return {
            "inactivacion_viral": self.proceso.a_dict(),
            "hallazgos": [h.a_dict() for h in self.hallazgos],
        }


def auditar_inactivacion_viral(
    proceso: ProcesoInactivacionViral,
    especificaciones: Mapping[str, Especificacion],
) -> ReporteInactivacionViral:
    """Contrasta parametros de proceso y factores de reduccion declarados.

    Los desvios en depuracion viral entran como CRITICA: es la barrera que separa
    al paciente de un contaminante adventicio, y ningun otro control del dossier
    la compensa.
    """
    hallazgos: list[Hallazgo] = []

    faltante = campo_ausente("Metodo de inactivacion viral", proceso.metodo, ETIQUETAS)
    if faltante is not None:
        hallazgos.append(faltante)

    sin_estudio = respaldo_documental(
        parametro="Validacion de remocion viral",
        referencia=proceso.estudio_referencia,
        descripcion_esperada="el estudio de validacion de remocion viral que sustenta los factores de reduccion declarados",
        etiquetas=ETIQUETAS,
        severidad=Severidad.CRITICA,
    )
    if sin_estudio is not None:
        hallazgos.append(sin_estudio)

    hallazgos.extend(
        auditar(
            [
                ParametroAuditado(
                    medicion=m,
                    especificacion=especificaciones.get(m.parametro),
                    severidad_si_desvia=Severidad.CRITICA,
                )
                for m in proceso.parametros_proceso
            ],
            etiquetas=ETIQUETAS,
        )
    )

    if not proceso.etapas:
        hallazgos.append(
            Hallazgo(
                parametro="Factores de reduccion viral",
                clase=ClaseHallazgo.RESULTADO_NO_SUMINISTRADO,
                severidad=Severidad.CRITICA,
                observacion=(
                    "El expediente no declara ninguna etapa con su factor de "
                    "reduccion viral. Sin LRV por etapa no hay capacidad de "
                    "depuracion demostrada."
                ),
                etiquetas=ETIQUETAS,
            )
        )

    for etapa in proceso.etapas:
        hallazgos.extend(
            auditar(
                [
                    ParametroAuditado(
                        medicion=etapa.lrv,
                        especificacion=especificaciones.get(etapa.lrv.parametro),
                        severidad_si_desvia=Severidad.CRITICA,
                    )
                ],
                etiquetas=ETIQUETAS + (f"etapa:{etapa.nombre}",),
            )
        )
        if etapa.lrv.presente and not etapa.declara_virus_modelo:
            hallazgos.append(
                Hallazgo(
                    parametro=f"Virus modelo de la etapa '{etapa.nombre}'",
                    clase=ClaseHallazgo.NO_COMPARABLE,
                    severidad=Severidad.ALTA,
                    observacion=(
                        f"La etapa '{etapa.nombre}' declara un factor de reduccion de "
                        f"{etapa.lrv.valor.exigir()} pero no dice sobre que virus "
                        f"modelo se obtuvo. Un LRV sin virus modelo no es contrastable: "
                        f"la capacidad de depuracion depende de si el virus es "
                        f"envuelto o no, de su tamano y de su resistencia."
                    ),
                    etiquetas=ETIQUETAS + (f"etapa:{etapa.nombre}",),
                )
            )

    return ReporteInactivacionViral(proceso=proceso, hallazgos=tuple(hallazgos))
