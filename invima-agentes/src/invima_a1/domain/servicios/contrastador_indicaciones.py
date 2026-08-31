"""Contraste entre la indicacion solicitada en Colombia y las aprobadas afuera.

Este es el nucleo del reliance regulatorio: la mayoria de moleculas nuevas ya
fueron evaluadas por FDA, EMA, MHRA o Health Canada. El sistema muestra la
relacion entre lo que se pide aca y lo que se aprobo alla, con su fuente.

Nunca emite juicio de aprobacion. Describe la relacion y cita. El evaluador
concluye.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..modelos import AprobacionAgencia
from .normalizacion import sin_tildes


class ClaseContraste(StrEnum):
    COINCIDENTE = "COINCIDENTE"
    """La indicacion solicitada equivale a la aprobada."""

    MAS_AMPLIA = "MAS_AMPLIA"
    """Lo solicitado en Colombia excede el alcance aprobado por la agencia."""

    MAS_RESTRINGIDA = "MAS_RESTRINGIDA"
    """Lo solicitado es un subconjunto de lo aprobado por la agencia."""

    SIN_CORRESPONDENCIA = "SIN_CORRESPONDENCIA"
    """No se identifica relacion entre ambas indicaciones."""

    NO_EVALUABLE = "NO_EVALUABLE"
    """Falta informacion para establecer la relacion."""


_VACIAS = frozenset(
    {
        "en", "de", "del", "la", "el", "los", "las", "y", "o", "para", "con",
        "adultos", "adulto", "pacientes", "paciente", "tratamiento", "the",
        "in", "of", "and", "for", "adults", "patients", "treatment", "a",
    }
)


def _terminos(texto: str) -> frozenset[str]:
    limpio = sin_tildes(texto).lower()
    limpio = "".join(c if c.isalnum() or c.isspace() else " " for c in limpio)
    return frozenset(t for t in limpio.split() if t and t not in _VACIAS and len(t) > 2)


@dataclass(frozen=True, slots=True)
class ContrasteIndicacion:
    agencia: str
    indicacion_solicitada: str
    indicacion_aprobada: str
    clase: ClaseContraste
    observacion: str
    fuente: str | None = None


@dataclass(frozen=True, slots=True)
class ReporteCoincidenciaInternacional:
    molecula: str
    agencias_que_aprobaron: tuple[str, ...]
    contrastes: tuple[ContrasteIndicacion, ...]
    aprobaciones_declaradas_no_verificadas: tuple[str, ...] = ()

    @property
    def hay_indicacion_mas_amplia(self) -> bool:
        return any(c.clase is ClaseContraste.MAS_AMPLIA for c in self.contrastes)


def clasificar_contraste(solicitada: str, aprobada: str) -> ClaseContraste:
    """Compara dos indicaciones por solapamiento de terminos clinicos.

    Deliberadamente conservador: ante duda devuelve SIN_CORRESPONDENCIA para que
    el evaluador lo revise, en vez de afirmar una equivalencia que no consta.
    """
    a = _terminos(solicitada)
    b = _terminos(aprobada)
    if not a or not b:
        return ClaseContraste.NO_EVALUABLE
    if a == b:
        return ClaseContraste.COINCIDENTE

    comunes = a & b
    if not comunes:
        return ClaseContraste.SIN_CORRESPONDENCIA

    cobertura_solicitada = len(comunes) / len(a)
    cobertura_aprobada = len(comunes) / len(b)

    if cobertura_solicitada >= 0.8 and cobertura_aprobada >= 0.8:
        return ClaseContraste.COINCIDENTE
    if cobertura_aprobada >= 0.8 > cobertura_solicitada:
        return ClaseContraste.MAS_AMPLIA
    if cobertura_solicitada >= 0.8 > cobertura_aprobada:
        return ClaseContraste.MAS_RESTRINGIDA
    return ClaseContraste.SIN_CORRESPONDENCIA


_OBSERVACIONES: dict[ClaseContraste, str] = {
    ClaseContraste.COINCIDENTE: (
        "La indicacion solicitada para Colombia corresponde a la aprobada por {agencia}."
    ),
    ClaseContraste.MAS_AMPLIA: (
        "La indicacion solicitada para Colombia abarca supuestos que no figuran en la "
        "aprobacion de {agencia}. Conviene revisar el sustento del alcance adicional."
    ),
    ClaseContraste.MAS_RESTRINGIDA: (
        "La indicacion solicitada para Colombia es mas acotada que la aprobada por "
        "{agencia}."
    ),
    ClaseContraste.SIN_CORRESPONDENCIA: (
        "No se identifica correspondencia entre la indicacion solicitada y la aprobada "
        "por {agencia}. Requiere lectura directa del evaluador."
    ),
    ClaseContraste.NO_EVALUABLE: (
        "Informacion insuficiente para contrastar la indicacion contra {agencia}."
    ),
}


def contrastar_indicaciones(
    molecula: str,
    indicacion_solicitada: str | None,
    aprobaciones: tuple[AprobacionAgencia, ...],
) -> ReporteCoincidenciaInternacional:
    """Construye el reporte de coincidencia internacional."""
    contrastes: list[ContrasteIndicacion] = []
    agencias_verificadas: list[str] = []
    declaradas_sin_verificar: list[str] = []

    for aprobacion in aprobaciones:
        if aprobacion.verificada_en_fuente:
            agencias_verificadas.append(aprobacion.agencia)
        elif aprobacion.declarada_por_solicitante:
            declaradas_sin_verificar.append(aprobacion.agencia)

        aprobada = aprobacion.indicacion_aprobada.valor
        if not indicacion_solicitada or not aprobada:
            clase = ClaseContraste.NO_EVALUABLE
        else:
            clase = clasificar_contraste(indicacion_solicitada, aprobada)

        fuente = None
        if aprobacion.indicacion_aprobada.traza:
            fuente = aprobacion.indicacion_aprobada.traza.descripcion

        contrastes.append(
            ContrasteIndicacion(
                agencia=aprobacion.agencia,
                indicacion_solicitada=indicacion_solicitada or "No suministrada",
                indicacion_aprobada=aprobada or "No disponible",
                clase=clase,
                observacion=_OBSERVACIONES[clase].format(agencia=aprobacion.agencia),
                fuente=fuente,
            )
        )

    return ReporteCoincidenciaInternacional(
        molecula=molecula,
        agencias_que_aprobaron=tuple(agencias_verificadas),
        contrastes=tuple(contrastes),
        aprobaciones_declaradas_no_verificadas=tuple(declaradas_sin_verificar),
    )
