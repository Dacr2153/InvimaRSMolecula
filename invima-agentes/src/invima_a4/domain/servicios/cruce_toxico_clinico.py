"""Cruce entre el organo blanco no clinico y las senales poscomercializacion.

Dos operaciones distintas, y conviene no confundirlas:

1. **Coincidencia de sistema u organo.** Si la toxicologia animal identifico el
   higado y una senal poscomercializacion afecta el sistema hepatobiliar, el
   agente reporta que ambos apuntan al mismo sistema. Reporta la coincidencia,
   **no una relacion causal**: afirmar que el hallazgo animal explica la senal
   humana es un juicio toxicologico que firma el evaluador.

2. **Senal ausente del plan de gestion de riesgos.** Comparar la lista de
   senales del PBRER contra la lista de riesgos del PGR es una diferencia de
   conjuntos. El cruce es **lexico**, con una tabla de sinonimos declarada aqui
   abajo, y por eso cada hallazgo dice que la busqueda fue por termino y que
   corresponde confirmarla en el documento. Un cruce lexico puede fallar; lo que
   no puede es fallar en silencio.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import Any, Iterable

from ..modelos import ClaseHallazgo, Hallazgo, Severidad
from ..valores import Dato

ETIQUETAS = ("cruce_toxico_clinico",)

#: Vocabulario curado por el agente para llevar terminos distintos al mismo
#: sistema. No proviene del expediente: es una tabla del sistema, inspeccionable
#: y ampliable, y su uso queda dicho en el texto de cada hallazgo.
SINONIMOS_SISTEMA_ORGANO: dict[str, tuple[str, ...]] = {
    "hepatobiliar": (
        "higado", "hepatico", "hepatica", "hepatotoxico", "hepatobiliar",
        "transaminasas", "alt", "ast", "bilirrubina", "hiperbilirrubinemia",
        "colecistitis", "vesicula", "colestasis", "ictericia",
    ),
    "reproductivo": (
        "reproductivo", "reproductiva", "embarazo", "gestacion", "gestante",
        "fetal", "feto", "embriofetal", "teratogeno", "malformacion",
        "malformaciones", "aborto", "abortos", "placentaria",
    ),
    "hematologico": (
        "hematologico", "hematologica", "plaquetas", "plaquetario",
        "trombocitopenia", "anemia", "neutropenia", "leucopenia",
    ),
    "inmunologico": (
        "inmunologico", "inmunologica", "anafilactica", "anafilaxia",
        "hipersensibilidad", "alergica", "alergenico",
    ),
    "renal": ("renal", "rinon", "nefrotoxico", "creatinina", "nefropatia"),
    "cardiovascular": (
        "cardiaco", "cardiaca", "cardiovascular", "arritmia", "miocardio",
    ),
    "respiratorio": ("pulmonar", "pulmon", "respiratorio", "respiratoria"),
}


def _sin_tildes(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


def _tokens(texto: str) -> set[str]:
    limpio = _sin_tildes(texto).casefold()
    crudos = "".join(c if c.isalnum() else " " for c in limpio).split()
    return {t for t in crudos if len(t) >= 2}


def sistemas_de(texto: str) -> frozenset[str]:
    """Sistemas u organos que menciona un texto, segun la tabla de sinonimos."""
    tokens = _tokens(texto)
    hallados = {
        sistema
        for sistema, terminos in SINONIMOS_SISTEMA_ORGANO.items()
        if tokens & set(terminos)
    }
    return frozenset(hallados)


def _sistemas_de_datos(datos: Iterable[Dato[str] | None]) -> frozenset[str]:
    sistemas: set[str] = set()
    for dato in datos:
        if dato is not None and dato.presente:
            sistemas |= sistemas_de(str(dato.exigir()))
    return frozenset(sistemas)


@dataclass(frozen=True, slots=True)
class PlanGestionRiesgos:
    """Riesgos que el solicitante lista en su plan de gestion de riesgos."""

    version: Dato[str]
    riesgos_listados: tuple[Dato[str], ...] = field(default_factory=tuple)

    def a_dict(self) -> dict[str, Any]:
        return {
            "version": self.version.a_dict(),
            "riesgos_listados": [r.a_dict() for r in self.riesgos_listados],
        }

    @property
    def sistemas_cubiertos(self) -> frozenset[str]:
        return _sistemas_de_datos(self.riesgos_listados)


@dataclass(frozen=True, slots=True)
class Coincidencia:
    sistema: str
    origen_no_clinico: str
    senal_poscomercializacion: str

    def a_dict(self) -> dict[str, Any]:
        return {
            "sistema": self.sistema,
            "hallazgo_no_clinico": self.origen_no_clinico,
            "senal_poscomercializacion": self.senal_poscomercializacion,
        }


@dataclass(frozen=True, slots=True)
class ReporteCruce:
    coincidencias: tuple[Coincidencia, ...]
    senales_sin_mencion_en_pgr: tuple[str, ...]
    hallazgos: tuple[Hallazgo, ...]

    def a_dict(self) -> dict[str, Any]:
        return {
            "coincidencias_de_sistema": [c.a_dict() for c in self.coincidencias],
            "senales_sin_mencion_en_el_pgr": list(self.senales_sin_mencion_en_pgr),
            "metodo_de_cruce": (
                "Coincidencia lexica sobre una tabla de sinonimos del sistema. "
                "Requiere confirmacion del evaluador en el documento."
            ),
            "hallazgos": [h.a_dict() for h in self.hallazgos],
        }


def cruzar(
    organos_blanco_no_clinicos: tuple[Dato[str], ...],
    senales: tuple[Any, ...],
    plan: PlanGestionRiesgos | None,
) -> ReporteCruce:
    """Cruza organos blanco, senales del PBRER y riesgos listados en el PGR."""
    hallazgos: list[Hallazgo] = []
    coincidencias: list[Coincidencia] = []

    sistemas_no_clinicos: dict[str, str] = {}
    for dato in organos_blanco_no_clinicos:
        if dato is None or not dato.presente:
            continue
        texto = str(dato.exigir())
        for sistema in sistemas_de(texto):
            sistemas_no_clinicos.setdefault(sistema, texto)

    for senal in senales:
        descripcion = (
            str(senal.descripcion.exigir()) if senal.descripcion.presente else ""
        )
        organo = (
            str(senal.sistema_organo.exigir())
            if senal.sistema_organo is not None and senal.sistema_organo.presente
            else ""
        )
        sistemas_senal = sistemas_de(f"{descripcion} {organo}")
        for sistema in sistemas_senal & set(sistemas_no_clinicos):
            coincidencias.append(
                Coincidencia(
                    sistema=sistema,
                    origen_no_clinico=sistemas_no_clinicos[sistema],
                    senal_poscomercializacion=senal.identificador,
                )
            )
            hallazgos.append(
                Hallazgo(
                    parametro=f"Coincidencia de sistema '{sistema}'",
                    clase=ClaseHallazgo.TENDENCIA_ADVERSA,
                    severidad=Severidad.ALTA,
                    observacion=(
                        f"El organo blanco identificado en la evidencia no clinica "
                        f"(\"{sistemas_no_clinicos[sistema]}\") y la senal "
                        f"poscomercializacion '{senal.identificador}' "
                        f"(\"{descripcion}\") apuntan al mismo sistema ({sistema}). El "
                        f"agente reporta la coincidencia de sistema; establecer si "
                        f"existe relacion entre ambos hallazgos es un juicio "
                        f"toxicologico del evaluador. La coincidencia se determino por "
                        f"termino, sobre la tabla de sinonimos del sistema."
                    ),
                    etiquetas=ETIQUETAS + (f"sistema:{sistema}",),
                )
            )

    if plan is None:
        hallazgos.append(
            Hallazgo(
                parametro="Plan de gestion de riesgos",
                clase=ClaseHallazgo.RESULTADO_NO_SUMINISTRADO,
                severidad=Severidad.CRITICA,
                observacion=(
                    "El expediente no aporta plan de gestion de riesgos. Sin el no hay "
                    "contra que cotejar las senales del informe periodico."
                ),
                etiquetas=ETIQUETAS + ("pgr",),
            )
        )
        return ReporteCruce(
            coincidencias=tuple(coincidencias),
            senales_sin_mencion_en_pgr=tuple(s.identificador for s in senales),
            hallazgos=tuple(hallazgos),
        )

    cubiertos = plan.sistemas_cubiertos
    sin_mencion: list[str] = []
    for senal in senales:
        descripcion = (
            str(senal.descripcion.exigir()) if senal.descripcion.presente else ""
        )
        organo = (
            str(senal.sistema_organo.exigir())
            if senal.sistema_organo is not None and senal.sistema_organo.presente
            else ""
        )
        sistemas_senal = sistemas_de(f"{descripcion} {organo}")
        if sistemas_senal and (sistemas_senal & cubiertos):
            continue
        sin_mencion.append(senal.identificador)
        detalle_sistema = (
            f" (sistema {', '.join(sorted(sistemas_senal))})" if sistemas_senal else ""
        )
        hallazgos.append(
            Hallazgo(
                parametro=f"Senal '{senal.identificador}' en el plan de gestion de riesgos",
                clase=ClaseHallazgo.RESULTADO_NO_SUMINISTRADO,
                severidad=Severidad.CRITICA,
                observacion=(
                    f"La senal '{senal.identificador}' (\"{descripcion}\")"
                    f"{detalle_sistema} figura en el informe periodico pero no se hallo "
                    f"mencion equivalente entre los {len(plan.riesgos_listados)} riesgos "
                    f"listados en el plan de gestion de riesgos "
                    f"({plan.version.valor or 'version no declarada'}). La busqueda fue "
                    f"lexica sobre la tabla de sinonimos del sistema: corresponde al "
                    f"evaluador confirmar la ausencia en el documento antes de "
                    f"requerirla al solicitante."
                ),
                etiquetas=ETIQUETAS + ("pgr", f"senal:{senal.identificador}"),
            )
        )

    return ReporteCruce(
        coincidencias=tuple(coincidencias),
        senales_sin_mencion_en_pgr=tuple(sin_mencion),
        hallazgos=tuple(hallazgos),
    )
