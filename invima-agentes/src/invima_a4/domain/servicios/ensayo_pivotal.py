"""Auditoria metodologica del ensayo clinico pivotal (Modulo 5.3.5).

El agente no juzga si el medicamento sirve. Verifica que el expediente diga lo
que hace falta para que un evaluador pueda juzgarlo, y que los numeros del
propio documento concuerden entre si:

- El esquema PICO esta completo? Un desenlace sin comparador no se lee.
- La diferencia declarada entre brazos es la resta de los brazos declarados?
- Los n de cada brazo suman el n total?
- **El alfa preespecificado esta declarado?** Sin el no hay contra que juzgar un
  valor p, y el agente NO asume 0.05: asumirlo es escribirle el protocolo al
  solicitante.
- Si se declaran varios desenlaces secundarios con significancia, se describe
  el control de multiplicidad? Sin el, la probabilidad de un falso positivo
  crece con cada desenlace y el expediente no lo dice.
- Se declara mas de una poblacion de analisis (por intencion de tratar y por
  protocolo)? Con una sola no hay como leer la robustez.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any

from ..modelos import ClaseHallazgo, Hallazgo, Medicion, Severidad, contrastar_derivado, derivar
from ..valores import Dato
from invima_nucleo.contraste import campo_ausente

ETIQUETAS = ("clinico", "ensayo_pivotal", "M5.3.5")

_AFIRMA_SIGNIFICANCIA = re.compile(
    r"(?<!no\s)\bsignificativ", re.IGNORECASE
)
_NIEGA_SIGNIFICANCIA = re.compile(r"\bno\s+signif", re.IGNORECASE)


class TipoDesenlace(StrEnum):
    PRIMARIO = "PRIMARIO"
    SECUNDARIO = "SECUNDARIO"
    SEGURIDAD = "SEGURIDAD"


@dataclass(frozen=True, slots=True)
class Desenlace:
    metrica: str
    tipo: TipoDesenlace
    valor_intervencion: Medicion | None = None
    valor_control: Medicion | None = None
    diferencia_declarada: Dato[Decimal] | None = None
    p_valor: Dato[Decimal] | None = None
    significancia_declarada: Dato[str] | None = None
    intervalo_confianza: Dato[str] | None = None

    def a_dict(self) -> dict[str, Any]:
        return {
            "metrica": self.metrica,
            "tipo": str(self.tipo),
            "valor_intervencion": (
                self.valor_intervencion.a_dict() if self.valor_intervencion else None
            ),
            "valor_control": (
                self.valor_control.a_dict() if self.valor_control else None
            ),
            "diferencia_declarada": (
                self.diferencia_declarada.a_dict() if self.diferencia_declarada else None
            ),
            "p_valor": self.p_valor.a_dict() if self.p_valor else None,
            "significancia_declarada": (
                self.significancia_declarada.a_dict()
                if self.significancia_declarada
                else None
            ),
            "intervalo_confianza": (
                self.intervalo_confianza.a_dict() if self.intervalo_confianza else None
            ),
        }


@dataclass(frozen=True, slots=True)
class EnsayoPivotal:
    estudio_id: Dato[str]
    registro_publico: Dato[str]
    fase: Dato[str]
    diseno: Dato[str]
    poblacion: Dato[str]
    intervencion: Dato[str]
    comparador: Dato[str]
    duracion_semanas: Medicion | None = None
    n_total: Medicion | None = None
    n_intervencion: Medicion | None = None
    n_control: Medicion | None = None
    alfa_prespecificado: Dato[Decimal] | None = None
    poder_declarado: Dato[Decimal] | None = None
    diferencia_del_calculo_de_poder: Medicion | None = None
    control_multiplicidad: Dato[str] | None = None
    poblaciones_de_analisis: tuple[Dato[str], ...] = field(default_factory=tuple)
    desenlaces: tuple[Desenlace, ...] = field(default_factory=tuple)

    def a_dict(self) -> dict[str, Any]:
        return {
            "estudio_id": self.estudio_id.a_dict(),
            "registro_publico": self.registro_publico.a_dict(),
            "fase": self.fase.a_dict(),
            "diseno": self.diseno.a_dict(),
            "pico": {
                "poblacion": self.poblacion.a_dict(),
                "intervencion": self.intervencion.a_dict(),
                "comparador": self.comparador.a_dict(),
                "desenlaces": [d.a_dict() for d in self.desenlaces],
            },
            "duracion_semanas": (
                self.duracion_semanas.a_dict() if self.duracion_semanas else None
            ),
            "n_total": self.n_total.a_dict() if self.n_total else None,
            "n_intervencion": (
                self.n_intervencion.a_dict() if self.n_intervencion else None
            ),
            "n_control": self.n_control.a_dict() if self.n_control else None,
            "alfa_prespecificado": (
                self.alfa_prespecificado.a_dict() if self.alfa_prespecificado else None
            ),
            "poder_declarado": (
                self.poder_declarado.a_dict() if self.poder_declarado else None
            ),
            "diferencia_del_calculo_de_poder": (
                self.diferencia_del_calculo_de_poder.a_dict()
                if self.diferencia_del_calculo_de_poder
                else None
            ),
            "control_multiplicidad": (
                self.control_multiplicidad.a_dict() if self.control_multiplicidad else None
            ),
            "poblaciones_de_analisis": [
                p.a_dict() for p in self.poblaciones_de_analisis
            ],
        }

    def desenlaces_de(self, tipo: TipoDesenlace) -> tuple[Desenlace, ...]:
        return tuple(d for d in self.desenlaces if d.tipo is tipo)


@dataclass(frozen=True, slots=True)
class ReporteEnsayo:
    ensayo: EnsayoPivotal | None
    hallazgos: tuple[Hallazgo, ...]

    def a_dict(self) -> dict[str, Any]:
        return {
            "ensayo_pivotal": self.ensayo.a_dict() if self.ensayo else None,
            "hallazgos": [h.a_dict() for h in self.hallazgos],
        }


def _afirma_significancia(dato: Dato[str] | None) -> bool:
    if dato is None or not dato.presente:
        return False
    texto = str(dato.exigir())
    if _NIEGA_SIGNIFICANCIA.search(texto):
        return False
    return bool(_AFIRMA_SIGNIFICANCIA.search(texto))


def _pico_completo(ensayo: EnsayoPivotal) -> list[Hallazgo]:
    hallazgos: list[Hallazgo] = []
    for nombre, dato in (
        ("Poblacion del ensayo (P del esquema PICO)", ensayo.poblacion),
        ("Intervencion del ensayo (I del esquema PICO)", ensayo.intervencion),
        ("Comparador del ensayo (C del esquema PICO)", ensayo.comparador),
        ("Registro publico del ensayo", ensayo.registro_publico),
        ("Diseno del ensayo", ensayo.diseno),
    ):
        faltante = campo_ausente(nombre, dato, ETIQUETAS)
        if faltante is not None:
            hallazgos.append(faltante)

    if not ensayo.desenlaces_de(TipoDesenlace.PRIMARIO):
        hallazgos.append(
            Hallazgo(
                parametro="Desenlace primario (O del esquema PICO)",
                clase=ClaseHallazgo.RESULTADO_NO_SUMINISTRADO,
                severidad=Severidad.CRITICA,
                observacion=(
                    "El expediente no declara ningun desenlace primario para el "
                    "ensayo pivotal. Sin desenlace primario preespecificado no hay "
                    "hipotesis que el ensayo haya puesto a prueba."
                ),
                etiquetas=ETIQUETAS,
            )
        )
    return hallazgos


def _aritmetica_de_brazos(ensayo: EnsayoPivotal) -> list[Hallazgo]:
    hallazgos: list[Hallazgo] = []
    if (
        ensayo.n_intervencion is not None
        and ensayo.n_control is not None
        and ensayo.n_intervencion.presente
        and ensayo.n_control.presente
    ):
        derivado = derivar(
            nombre="Poblacion total del ensayo",
            formula="n_intervencion + n_control",
            componentes=(
                ("n_intervencion", ensayo.n_intervencion.valor.exigir()),
                ("n_control", ensayo.n_control.valor.exigir()),
            ),
            operacion=lambda a, b: a + b,
            unidad="pacientes",
        )
        contraste = contrastar_derivado(
            derivado,
            ensayo.n_total.valor if ensayo.n_total is not None else None,
            severidad_si_discrepa=Severidad.ALTA,
            etiquetas=ETIQUETAS,
        )
        if contraste is not None:
            hallazgos.append(contraste)
    return hallazgos


def _auditar_desenlace(desenlace: Desenlace, ensayo: EnsayoPivotal) -> list[Hallazgo]:
    etiquetas = ETIQUETAS + (f"desenlace:{desenlace.tipo}",)
    hallazgos: list[Hallazgo] = []

    # La diferencia declarada tiene que ser la resta de los brazos declarados.
    if (
        desenlace.valor_intervencion is not None
        and desenlace.valor_control is not None
        and desenlace.valor_intervencion.presente
        and desenlace.valor_control.presente
    ):
        derivado = derivar(
            nombre=f"Diferencia entre brazos en '{desenlace.metrica}'",
            formula="valor_intervencion - valor_control",
            componentes=(
                ("valor_intervencion", desenlace.valor_intervencion.valor.exigir()),
                ("valor_control", desenlace.valor_control.valor.exigir()),
            ),
            operacion=lambda a, b: a - b,
            unidad=desenlace.valor_intervencion.unidad,
        )
        contraste = contrastar_derivado(
            derivado,
            desenlace.diferencia_declarada,
            severidad_si_discrepa=Severidad.ALTA,
            etiquetas=etiquetas,
        )
        if contraste is not None:
            hallazgos.append(contraste)

    if desenlace.p_valor is None or not desenlace.p_valor.presente:
        severidad = (
            Severidad.ALTA if desenlace.tipo is TipoDesenlace.PRIMARIO else Severidad.MEDIA
        )
        hallazgos.append(
            Hallazgo(
                parametro=f"Valor p de '{desenlace.metrica}'",
                clase=ClaseHallazgo.RESULTADO_NO_SUMINISTRADO,
                severidad=severidad,
                observacion=(
                    f"El expediente reporta el desenlace '{desenlace.metrica}' sin "
                    f"valor p. La diferencia entre brazos no se puede situar respecto "
                    f"del azar."
                ),
                etiquetas=etiquetas,
            )
        )
        return hallazgos

    p = desenlace.p_valor.exigir()

    if ensayo.alfa_prespecificado is None or not ensayo.alfa_prespecificado.presente:
        hallazgos.append(
            Hallazgo(
                parametro=f"Umbral de decision para '{desenlace.metrica}'",
                clase=ClaseHallazgo.ESPECIFICACION_NO_DECLARADA,
                severidad=Severidad.MEDIA,
                observacion=(
                    f"El desenlace '{desenlace.metrica}' reporta p = {p} pero el "
                    f"expediente no declara el nivel de significancia preespecificado "
                    f"del protocolo. El agente no asume 0.05: el umbral lo fija el "
                    f"protocolo del ensayo y debe constar."
                ),
                etiquetas=etiquetas,
            )
        )
        return hallazgos

    alfa = ensayo.alfa_prespecificado.exigir()
    bajo_umbral = p < alfa
    afirma = _afirma_significancia(desenlace.significancia_declarada)

    if afirma and not bajo_umbral:
        hallazgos.append(
            Hallazgo(
                parametro=f"Significancia declarada de '{desenlace.metrica}'",
                clase=ClaseHallazgo.DISCREPANCIA_ARITMETICA,
                severidad=Severidad.ALTA,
                observacion=(
                    f"El expediente califica '{desenlace.metrica}' como significativo "
                    f"pero su valor p ({p}) no queda por debajo del nivel "
                    f"preespecificado ({alfa})."
                ),
                etiquetas=etiquetas,
            )
        )
    else:
        hallazgos.append(
            Hallazgo(
                parametro=f"Valor p de '{desenlace.metrica}'",
                clase=(
                    ClaseHallazgo.DENTRO_DE_ESPECIFICACION
                    if bajo_umbral
                    else ClaseHallazgo.FUERA_DE_ESPECIFICACION
                ),
                severidad=Severidad.INFORMATIVA
                if bajo_umbral
                else Severidad.MEDIA,
                observacion=(
                    f"'{desenlace.metrica}' ({desenlace.tipo}): p = {p} "
                    f"{'por debajo' if bajo_umbral else 'no queda por debajo'} del "
                    f"nivel de significancia preespecificado ({alfa})."
                ),
                etiquetas=etiquetas,
            )
        )

    # Un p no significativo no demuestra ausencia de efecto. Si el expediente lo
    # lee asi sin intervalo de confianza, se senala.
    if (
        not bajo_umbral
        and desenlace.significancia_declarada is not None
        and desenlace.significancia_declarada.presente
        and (desenlace.intervalo_confianza is None or not desenlace.intervalo_confianza.presente)
    ):
        hallazgos.append(
            Hallazgo(
                parametro=f"Lectura de la ausencia de significancia en '{desenlace.metrica}'",
                clase=ClaseHallazgo.NO_COMPARABLE,
                severidad=Severidad.MEDIA,
                observacion=(
                    f"El expediente describe '{desenlace.metrica}' con p = {p} como "
                    f"sin diferencia entre brazos. Un valor p por encima del umbral no "
                    f"demuestra ausencia de efecto: solo indica que el estudio no la "
                    f"descarto. Sin intervalo de confianza declarado no se puede saber "
                    f"que magnitud de diferencia queda todavia compatible con los datos."
                ),
                etiquetas=etiquetas,
            )
        )

    return hallazgos


def _multiplicidad(ensayo: EnsayoPivotal) -> list[Hallazgo]:
    secundarios_afirmados = [
        d
        for d in ensayo.desenlaces_de(TipoDesenlace.SECUNDARIO)
        if _afirma_significancia(d.significancia_declarada)
    ]
    if len(secundarios_afirmados) < 2:
        return []
    if ensayo.control_multiplicidad is not None and ensayo.control_multiplicidad.presente:
        return []
    nombres = ", ".join(f"'{d.metrica}'" for d in secundarios_afirmados)
    return [
        Hallazgo(
            parametro="Control de multiplicidad",
            clase=ClaseHallazgo.RESULTADO_NO_SUMINISTRADO,
            severidad=Severidad.MEDIA,
            observacion=(
                f"El expediente declara {len(secundarios_afirmados)} desenlaces "
                f"secundarios como significativos ({nombres}) sin describir el "
                f"procedimiento de control de multiplicidad. Al contrastar varias "
                f"hipotesis con el mismo umbral, la probabilidad de al menos un "
                f"falso positivo crece con cada contraste."
            ),
            etiquetas=ETIQUETAS + ("multiplicidad",),
        )
    ]


def _poblaciones_de_analisis(ensayo: EnsayoPivotal) -> list[Hallazgo]:
    declaradas = [p for p in ensayo.poblaciones_de_analisis if p.presente]
    if len(declaradas) >= 2:
        return []
    return [
        Hallazgo(
            parametro="Poblaciones de analisis declaradas",
            clase=ClaseHallazgo.RESULTADO_NO_SUMINISTRADO,
            severidad=Severidad.MEDIA,
            observacion=(
                f"El expediente declara {len(declaradas)} poblacion(es) de analisis. "
                f"Sin al menos dos (por intencion de tratar y por protocolo) no hay "
                f"como leer si el resultado se sostiene al cambiar el criterio de "
                f"inclusion en el analisis."
            ),
            etiquetas=ETIQUETAS,
        )
    ]


def _poder_y_efecto(ensayo: EnsayoPivotal) -> list[Hallazgo]:
    if ensayo.poder_declarado is None or not ensayo.poder_declarado.presente:
        return [
            Hallazgo(
                parametro="Poder estadistico declarado",
                clase=ClaseHallazgo.RESULTADO_NO_SUMINISTRADO,
                severidad=Severidad.MEDIA,
                observacion=(
                    "El expediente no declara el poder estadistico del ensayo ni la "
                    "diferencia que el tamano de muestra fue disenado para detectar. "
                    "Sin eso no se puede saber que magnitud de efecto el estudio "
                    "estaba en condiciones de encontrar."
                ),
                etiquetas=ETIQUETAS,
            )
        ]
    if (
        ensayo.diferencia_del_calculo_de_poder is None
        or not ensayo.diferencia_del_calculo_de_poder.presente
    ):
        return [
            Hallazgo(
                parametro="Diferencia usada en el calculo de poder",
                clase=ClaseHallazgo.RESULTADO_NO_SUMINISTRADO,
                severidad=Severidad.MEDIA,
                observacion=(
                    f"El expediente declara un poder de "
                    f"{ensayo.poder_declarado.exigir()} sin decir para que magnitud de "
                    f"diferencia. Un poder sin efecto de referencia no es "
                    f"interpretable."
                ),
                etiquetas=ETIQUETAS,
            )
        ]
    return []


def auditar_ensayo_pivotal(ensayo: EnsayoPivotal | None) -> ReporteEnsayo:
    if ensayo is None:
        return ReporteEnsayo(
            ensayo=None,
            hallazgos=(
                Hallazgo(
                    parametro="Ensayo clinico pivotal",
                    clase=ClaseHallazgo.RESULTADO_NO_SUMINISTRADO,
                    severidad=Severidad.CRITICA,
                    observacion=(
                        "El expediente no aporta ensayo clinico pivotal. No hay "
                        "evidencia clinica sobre la que el evaluador pueda pronunciarse."
                    ),
                    etiquetas=ETIQUETAS,
                ),
            ),
        )

    hallazgos: list[Hallazgo] = []
    hallazgos.extend(_pico_completo(ensayo))
    hallazgos.extend(_aritmetica_de_brazos(ensayo))
    for desenlace in ensayo.desenlaces:
        hallazgos.extend(_auditar_desenlace(desenlace, ensayo))
    hallazgos.extend(_multiplicidad(ensayo))
    hallazgos.extend(_poblaciones_de_analisis(ensayo))
    hallazgos.extend(_poder_y_efecto(ensayo))
    return ReporteEnsayo(ensayo=ensayo, hallazgos=tuple(hallazgos))
