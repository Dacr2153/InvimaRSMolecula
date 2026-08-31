"""Auditoria de inmunogenicidad: anticuerpos anti-farmaco y neutralizantes.

Dos verificaciones aritmeticas y una metodologica. Las aritmeticas: que las
incidencias declaradas salgan de sus casos y su denominador, y que los
neutralizantes sean un subconjunto de los anti-farmaco. La metodologica es la
que importa: **un valor p por encima del umbral no demuestra ausencia de
efecto**, y un expediente que lee "p = 0.52" como "no altera la eficacia" esta
dando por probada una hipotesis que su estudio solo dejo sin descartar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from ..modelos import ClaseHallazgo, Hallazgo, Medicion, Severidad, contrastar_derivado, derivar
from ..valores import Dato
from invima_nucleo.contraste import campo_ausente

ETIQUETAS = ("clinico", "inmunogenicidad", "M5.3")


@dataclass(frozen=True, slots=True)
class ImpactoDeclarado:
    """Lectura que el expediente hace del efecto de los anticuerpos."""

    metrica: str
    p_valor: Dato[Decimal] | None = None
    conclusion_declarada: Dato[str] | None = None
    intervalo_confianza: Dato[str] | None = None

    def a_dict(self) -> dict[str, Any]:
        return {
            "metrica": self.metrica,
            "p_valor": self.p_valor.a_dict() if self.p_valor else None,
            "conclusion_declarada": (
                self.conclusion_declarada.a_dict() if self.conclusion_declarada else None
            ),
            "intervalo_confianza": (
                self.intervalo_confianza.a_dict() if self.intervalo_confianza else None
            ),
        }


@dataclass(frozen=True, slots=True)
class Inmunogenicidad:
    ada_casos: Medicion | None = None
    ada_poblacion: Medicion | None = None
    ada_incidencia_declarada: Dato[Decimal] | None = None
    nab_casos: Medicion | None = None
    nab_poblacion: Medicion | None = None
    nab_incidencia_declarada: Dato[Decimal] | None = None
    ventana_aparicion: Dato[str] | None = None
    impactos: tuple[ImpactoDeclarado, ...] = field(default_factory=tuple)

    def a_dict(self) -> dict[str, Any]:
        return {
            "ada": {
                "casos": self.ada_casos.a_dict() if self.ada_casos else None,
                "poblacion": self.ada_poblacion.a_dict() if self.ada_poblacion else None,
                "incidencia_declarada_porcentaje": (
                    self.ada_incidencia_declarada.a_dict()
                    if self.ada_incidencia_declarada
                    else None
                ),
            },
            "nab": {
                "casos": self.nab_casos.a_dict() if self.nab_casos else None,
                "poblacion": self.nab_poblacion.a_dict() if self.nab_poblacion else None,
                "incidencia_declarada_porcentaje": (
                    self.nab_incidencia_declarada.a_dict()
                    if self.nab_incidencia_declarada
                    else None
                ),
            },
            "ventana_aparicion": (
                self.ventana_aparicion.a_dict() if self.ventana_aparicion else None
            ),
            "impactos_declarados": [i.a_dict() for i in self.impactos],
        }


@dataclass(frozen=True, slots=True)
class ReporteInmunogenicidad:
    inmunogenicidad: Inmunogenicidad | None
    hallazgos: tuple[Hallazgo, ...]

    def a_dict(self) -> dict[str, Any]:
        return {
            "inmunogenicidad": (
                self.inmunogenicidad.a_dict() if self.inmunogenicidad else None
            ),
            "hallazgos": [h.a_dict() for h in self.hallazgos],
        }


def _incidencia(
    etiqueta: str, casos: Medicion | None, poblacion: Medicion | None,
    declarada: Dato[Decimal] | None,
) -> Hallazgo | None:
    if casos is None or poblacion is None or not casos.presente or not poblacion.presente:
        return None
    derivado = derivar(
        nombre=f"Incidencia de {etiqueta}",
        formula="casos / poblacion * 100",
        componentes=(
            ("casos", casos.valor.exigir()),
            ("poblacion", poblacion.valor.exigir()),
        ),
        operacion=lambda c, p: c / p * Decimal(100),
        unidad="%",
    )
    return contrastar_derivado(
        derivado, declarada, severidad_si_discrepa=Severidad.MEDIA, etiquetas=ETIQUETAS
    )


def auditar_inmunogenicidad(
    inmunogenicidad: Inmunogenicidad | None,
) -> ReporteInmunogenicidad:
    if inmunogenicidad is None:
        return ReporteInmunogenicidad(
            inmunogenicidad=None,
            hallazgos=(
                Hallazgo(
                    parametro="Inmunogenicidad",
                    clase=ClaseHallazgo.RESULTADO_NO_SUMINISTRADO,
                    severidad=Severidad.ALTA,
                    observacion=(
                        "El expediente no aporta datos de inmunogenicidad. En un "
                        "medicamento biologico la respuesta de anticuerpos "
                        "anti-farmaco es un dato esperable del desarrollo clinico."
                    ),
                    etiquetas=ETIQUETAS,
                ),
            ),
        )

    hallazgos: list[Hallazgo] = []

    for etiqueta, casos, poblacion, declarada in (
        ("anticuerpos anti-farmaco (ADA)", inmunogenicidad.ada_casos,
         inmunogenicidad.ada_poblacion, inmunogenicidad.ada_incidencia_declarada),
        ("anticuerpos neutralizantes (NAb)", inmunogenicidad.nab_casos,
         inmunogenicidad.nab_poblacion, inmunogenicidad.nab_incidencia_declarada),
    ):
        hallazgo = _incidencia(etiqueta, casos, poblacion, declarada)
        if hallazgo is not None:
            hallazgos.append(hallazgo)

    # Los neutralizantes son un subconjunto de los anti-farmaco.
    if (
        inmunogenicidad.ada_casos is not None
        and inmunogenicidad.nab_casos is not None
        and inmunogenicidad.ada_casos.presente
        and inmunogenicidad.nab_casos.presente
    ):
        ada = inmunogenicidad.ada_casos.valor.exigir()
        nab = inmunogenicidad.nab_casos.valor.exigir()
        if nab > ada:
            hallazgos.append(
                Hallazgo(
                    parametro="Coherencia entre ADA y NAb",
                    clase=ClaseHallazgo.DISCREPANCIA_ARITMETICA,
                    severidad=Severidad.ALTA,
                    observacion=(
                        f"El expediente declara {nab} casos de anticuerpos "
                        f"neutralizantes sobre {ada} casos de anticuerpos "
                        f"anti-farmaco. Los neutralizantes son un subconjunto de los "
                        f"anti-farmaco: no puede haber mas de los primeros que de los "
                        f"segundos."
                    ),
                    etiquetas=ETIQUETAS,
                )
            )

    faltante = campo_ausente(
        "Ventana de aparicion de los anticuerpos",
        inmunogenicidad.ventana_aparicion,
        ETIQUETAS,
        severidad=Severidad.MEDIA,
    )
    if faltante is not None:
        hallazgos.append(faltante)

    for impacto in inmunogenicidad.impactos:
        if impacto.p_valor is None or not impacto.p_valor.presente:
            hallazgos.append(
                Hallazgo(
                    parametro=f"Impacto de los anticuerpos en '{impacto.metrica}'",
                    clase=ClaseHallazgo.RESULTADO_NO_SUMINISTRADO,
                    severidad=Severidad.MEDIA,
                    observacion=(
                        f"El expediente describe el efecto de los anticuerpos sobre "
                        f"'{impacto.metrica}' sin aportar el contraste que lo sustenta."
                    ),
                    etiquetas=ETIQUETAS,
                )
            )
            continue
        sin_intervalo = (
            impacto.intervalo_confianza is None
            or not impacto.intervalo_confianza.presente
        )
        declara_conclusion = (
            impacto.conclusion_declarada is not None
            and impacto.conclusion_declarada.presente
        )
        if declara_conclusion and sin_intervalo:
            hallazgos.append(
                Hallazgo(
                    parametro=f"Lectura del impacto en '{impacto.metrica}'",
                    clase=ClaseHallazgo.NO_COMPARABLE,
                    severidad=Severidad.MEDIA,
                    observacion=(
                        f"El expediente concluye sobre '{impacto.metrica}' "
                        f"(\"{impacto.conclusion_declarada.exigir()}\") a partir de un "
                        f"valor p de {impacto.p_valor.exigir()}, sin intervalo de "
                        f"confianza. Un contraste que no alcanza el umbral no "
                        f"demuestra que el efecto sea nulo; deja abierta la magnitud "
                        f"de efecto todavia compatible con los datos, y esa magnitud "
                        f"es la que el evaluador necesita para decidir si importa."
                    ),
                    etiquetas=ETIQUETAS,
                )
            )

    return ReporteInmunogenicidad(
        inmunogenicidad=inmunogenicidad, hallazgos=tuple(hallazgos)
    )
