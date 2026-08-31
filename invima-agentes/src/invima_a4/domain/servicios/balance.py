"""Insumos para el balance beneficio-riesgo. No el balance.

El borrador de especificacion de este agente terminaba clasificando el balance
como FAVORABLE CONDICIONADO y recomendando aprobacion con cinco condiciones.
Ponderar beneficio contra riesgo es el acto de juicio que define a la Comision
Revisora; un agente que lo hace no la asiste, la sustituye, y el articulo 7.1 lo
prohibe.

Lo que si es mecanizable, y es lo que hace este modulo: **ordenar la mesa**.
Poner de un lado los beneficios que el expediente declara con su contraste y su
folio, del otro los riesgos con su frecuencia y la mitigacion que el propio
solicitante propone, aparte lo que quedo sin dato, y traducir cada hallazgo
grave en una pregunta concreta que el evaluador tiene que responder. La suma no
la hace el agente.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from ..modelos import ClaseHallazgo, Hallazgo, Severidad
from ..valores import Dato

ETIQUETAS = ("balance",)


@dataclass(frozen=True, slots=True)
class BeneficioDeclarado:
    desenlace: str
    tipo: str
    valor_intervencion: Any = None
    valor_control: Any = None
    p_valor: Any = None
    umbral_prespecificado: Any = None
    queda_bajo_el_umbral: bool | None = None
    trazabilidad: dict[str, Any] | None = None

    def a_dict(self) -> dict[str, Any]:
        return {
            "desenlace": self.desenlace,
            "tipo": self.tipo,
            "valor_intervencion": self.valor_intervencion,
            "valor_control": self.valor_control,
            "p_valor": self.p_valor,
            "umbral_prespecificado": self.umbral_prespecificado,
            "queda_bajo_el_umbral_prespecificado": self.queda_bajo_el_umbral,
            "trazabilidad": self.trazabilidad,
        }


@dataclass(frozen=True, slots=True)
class RiesgoDeclarado:
    descripcion: str
    origen: str
    frecuencia: str | None = None
    mitigacion_declarada: str | None = None
    trazabilidad: dict[str, Any] | None = None

    def a_dict(self) -> dict[str, Any]:
        return {
            "descripcion": self.descripcion,
            "origen_de_la_evidencia": self.origen,
            "frecuencia_declarada": self.frecuencia,
            "mitigacion_declarada_por_el_solicitante": self.mitigacion_declarada,
            "trazabilidad": self.trazabilidad,
        }


@dataclass(frozen=True, slots=True)
class Incertidumbre:
    asunto: str
    motivo: str

    def a_dict(self) -> dict[str, Any]:
        return {"asunto": self.asunto, "motivo": self.motivo}


@dataclass(frozen=True, slots=True)
class InsumosBalance:
    beneficios: tuple[BeneficioDeclarado, ...] = field(default_factory=tuple)
    riesgos: tuple[RiesgoDeclarado, ...] = field(default_factory=tuple)
    incertidumbres: tuple[Incertidumbre, ...] = field(default_factory=tuple)
    preguntas_abiertas: tuple[str, ...] = field(default_factory=tuple)

    def a_dict(self) -> dict[str, Any]:
        return {
            "nota_de_alcance": (
                "Insumos para que el evaluador construya el balance. El agente no "
                "pondera beneficio contra riesgo ni propone un sentido para el "
                "tramite: ordena la evidencia declarada, senala lo que falta y "
                "formula las preguntas que quedan abiertas."
            ),
            "beneficios_declarados": [b.a_dict() for b in self.beneficios],
            "riesgos_declarados": [r.a_dict() for r in self.riesgos],
            "incertidumbres": [i.a_dict() for i in self.incertidumbres],
            "preguntas_abiertas_para_el_evaluador": list(self.preguntas_abiertas),
        }


_PLANTILLAS: dict[ClaseHallazgo, str] = {
    ClaseHallazgo.RESULTADO_NO_SUMINISTRADO: (
        "Falta en el expediente: {parametro}. Se requiere al solicitante o se "
        "decide con el dato ausente?"
    ),
    ClaseHallazgo.ESPECIFICACION_NO_DECLARADA: (
        "No hay criterio declarado contra el cual leer {parametro}. Lo fija el "
        "evaluador desde la norma aplicable o se requiere al solicitante?"
    ),
    ClaseHallazgo.DISCREPANCIA_ARITMETICA: (
        "Los numeros del expediente para {parametro} no concuerdan entre si. "
        "Cual de los dos vale, y afecta la lectura del resto del dossier?"
    ),
    ClaseHallazgo.FUERA_DE_ESPECIFICACION: (
        "{parametro} queda fuera del criterio declarado. Es admisible para esta "
        "indicacion y esta poblacion?"
    ),
    ClaseHallazgo.TENDENCIA_ADVERSA: (
        "{parametro} muestra una senal que el expediente no cierra. Que lectura "
        "merece y exige alguna condicion?"
    ),
    ClaseHallazgo.NO_COMPARABLE: (
        "{parametro} no es contrastable tal como viene declarado. Se requiere al "
        "solicitante en forma comparable?"
    ),
}


def preguntas_desde(hallazgos: Sequence[Hallazgo], limite: int = 20) -> tuple[str, ...]:
    """Traduce los hallazgos graves en preguntas concretas para el evaluador.

    Determinista: misma entrada, mismas preguntas y en el mismo orden.
    """
    preguntas: list[str] = []
    for hallazgo in hallazgos:
        if hallazgo.severidad not in (Severidad.CRITICA, Severidad.ALTA):
            continue
        plantilla = _PLANTILLAS.get(hallazgo.clase)
        if plantilla is None:
            continue
        pregunta = plantilla.format(parametro=hallazgo.parametro)
        if pregunta not in preguntas:
            preguntas.append(pregunta)
        if len(preguntas) >= limite:
            break
    return tuple(preguntas)


def incertidumbres_desde(hallazgos: Sequence[Hallazgo]) -> tuple[Incertidumbre, ...]:
    """Todo lo que el expediente dejo sin dato o sin criterio."""
    incertidumbres: list[Incertidumbre] = []
    vistos: set[str] = set()
    for hallazgo in hallazgos:
        if hallazgo.clase not in (
            ClaseHallazgo.RESULTADO_NO_SUMINISTRADO,
            ClaseHallazgo.ESPECIFICACION_NO_DECLARADA,
            ClaseHallazgo.NO_COMPARABLE,
        ):
            continue
        if hallazgo.parametro in vistos:
            continue
        vistos.add(hallazgo.parametro)
        incertidumbres.append(
            Incertidumbre(asunto=hallazgo.parametro, motivo=hallazgo.observacion)
        )
    return tuple(incertidumbres)


def armar_insumos(
    beneficios: Sequence[BeneficioDeclarado],
    riesgos: Sequence[RiesgoDeclarado],
    hallazgos: Sequence[Hallazgo],
) -> InsumosBalance:
    return InsumosBalance(
        beneficios=tuple(beneficios),
        riesgos=tuple(riesgos),
        incertidumbres=incertidumbres_desde(hallazgos),
        preguntas_abiertas=preguntas_desde(hallazgos),
    )
