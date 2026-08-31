"""Auditoria del informe periodico de beneficio-riesgo (PBRER, Modulo 7).

Una tasa poscomercializacion es un cociente entre dos numeros que el propio
informe declara. Por eso es el sitio del expediente donde un error de
denominador se atrapa sin salir del documento -- y donde mas dano hace, porque
una tasa diez veces menor de lo que corresponde cambia por completo como se lee
una senal.

El agente recalcula. Cuando el numero declarado no sale de sus componentes,
reporta los dos y el factor entre ellos, y si el porcentaje declarado se
reproduce con el OTRO denominador del informe, lo dice: confundir pacientes con
pacientes-ano es la forma habitual de ese error.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from ..modelos import ClaseHallazgo, Hallazgo, Medicion, Severidad, contrastar_derivado, derivar
from ..valores import Dato
from invima_nucleo.aritmetica import TOLERANCIA_RELATIVA
from invima_nucleo.contraste import campo_ausente

ETIQUETAS = ("farmacovigilancia", "PBRER", "M7")


@dataclass(frozen=True, slots=True)
class SenalSeguridad:
    identificador: str
    descripcion: Dato[str]
    casos: Medicion | None = None
    tasa_declarada_por_1000: Dato[Decimal] | None = None
    sistema_organo: Dato[str] | None = None
    factor_riesgo: Dato[str] | None = None
    gravedad: Dato[str] | None = None

    def a_dict(self) -> dict[str, Any]:
        return {
            "identificador": self.identificador,
            "descripcion": self.descripcion.a_dict(),
            "casos": self.casos.a_dict() if self.casos else None,
            "tasa_declarada_por_1000_pacientes_ano": (
                self.tasa_declarada_por_1000.a_dict()
                if self.tasa_declarada_por_1000
                else None
            ),
            "sistema_organo": (
                self.sistema_organo.a_dict() if self.sistema_organo else None
            ),
            "factor_riesgo": self.factor_riesgo.a_dict() if self.factor_riesgo else None,
            "gravedad": self.gravedad.a_dict() if self.gravedad else None,
        }


@dataclass(frozen=True, slots=True)
class InformePBRER:
    numero: Dato[str]
    periodo_meses: Medicion | None = None
    exposicion_pacientes_ano: Medicion | None = None
    pacientes_expuestos: Medicion | None = None
    eventos_totales: Medicion | None = None
    incidencia_general_declarada: Dato[Decimal] | None = None
    eventos_graves: Medicion | None = None
    incidencia_graves_declarada: Dato[Decimal] | None = None
    muertes: Medicion | None = None
    estado_investigacion_muertes: Dato[str] | None = None
    senales: tuple[SenalSeguridad, ...] = field(default_factory=tuple)

    def a_dict(self) -> dict[str, Any]:
        return {
            "numero": self.numero.a_dict(),
            "periodo_meses": self.periodo_meses.a_dict() if self.periodo_meses else None,
            "exposicion_pacientes_ano": (
                self.exposicion_pacientes_ano.a_dict()
                if self.exposicion_pacientes_ano
                else None
            ),
            "pacientes_expuestos": (
                self.pacientes_expuestos.a_dict() if self.pacientes_expuestos else None
            ),
            "eventos_totales": (
                self.eventos_totales.a_dict() if self.eventos_totales else None
            ),
            "incidencia_general_declarada_porcentaje": (
                self.incidencia_general_declarada.a_dict()
                if self.incidencia_general_declarada
                else None
            ),
            "eventos_graves": (
                self.eventos_graves.a_dict() if self.eventos_graves else None
            ),
            "incidencia_graves_declarada_porcentaje": (
                self.incidencia_graves_declarada.a_dict()
                if self.incidencia_graves_declarada
                else None
            ),
            "muertes": self.muertes.a_dict() if self.muertes else None,
            "estado_investigacion_muertes": (
                self.estado_investigacion_muertes.a_dict()
                if self.estado_investigacion_muertes
                else None
            ),
            "senales": [s.a_dict() for s in self.senales],
        }


@dataclass(frozen=True, slots=True)
class ReportePBRER:
    informe: InformePBRER | None
    hallazgos: tuple[Hallazgo, ...]

    def a_dict(self) -> dict[str, Any]:
        return {
            "pbrer": self.informe.a_dict() if self.informe else None,
            "hallazgos": [h.a_dict() for h in self.hallazgos],
        }


def _reproduce(declarado: Decimal, candidato: Decimal) -> bool:
    if candidato == 0:
        return declarado == 0
    return abs(declarado - candidato) / abs(candidato) <= TOLERANCIA_RELATIVA


def _incidencia_con_denominador_alterno(
    nombre: str,
    casos: Medicion | None,
    pacientes: Medicion | None,
    pacientes_ano: Medicion | None,
    declarada: Dato[Decimal] | None,
) -> Hallazgo | None:
    """Recalcula un porcentaje sobre pacientes y avisa si sale con pacientes-ano.

    Un porcentaje de incidencia se calcula sobre personas. Si el numero
    declarado solo se reproduce dividiendo por pacientes-ano, el informe esta
    presentando una tasa como si fuera una proporcion, y eso cambia como se lee.
    """
    if casos is None or not casos.presente or pacientes is None or not pacientes.presente:
        return None
    derivado = derivar(
        nombre=nombre,
        formula="casos / pacientes_expuestos * 100",
        componentes=(
            ("casos", casos.valor.exigir()),
            ("pacientes_expuestos", pacientes.valor.exigir()),
        ),
        operacion=lambda c, p: c / p * Decimal(100),
        unidad="%",
    )
    hallazgo = contrastar_derivado(
        derivado, declarada, severidad_si_discrepa=Severidad.MEDIA, etiquetas=ETIQUETAS
    )
    if hallazgo is None or hallazgo.clase is not ClaseHallazgo.DISCREPANCIA_ARITMETICA:
        return hallazgo
    if (
        pacientes_ano is None
        or not pacientes_ano.presente
        or declarada is None
        or not declarada.presente
    ):
        return hallazgo
    alterno = casos.valor.exigir() / pacientes_ano.valor.exigir() * Decimal(100)
    if not _reproduce(declarada.exigir(), alterno):
        return hallazgo
    return Hallazgo(
        parametro=hallazgo.parametro,
        clase=hallazgo.clase,
        severidad=Severidad.ALTA,
        observacion=(
            hallazgo.observacion
            + f" El valor declarado si se reproduce dividiendo por la exposicion en "
            f"pacientes-ano ({pacientes_ano.valor.exigir()}) en lugar de por el numero "
            f"de pacientes expuestos ({pacientes.valor.exigir()}): el informe presenta "
            f"como proporcion de pacientes lo que es una tasa por unidad de tiempo de "
            f"exposicion. No son la misma medida y no se leen igual."
        ),
        medicion=hallazgo.medicion,
        etiquetas=hallazgo.etiquetas + ("denominador",),
    )


def auditar_pbrer(informe: InformePBRER | None) -> ReportePBRER:
    if informe is None:
        return ReportePBRER(
            informe=None,
            hallazgos=(
                Hallazgo(
                    parametro="Informe periodico de beneficio-riesgo (PBRER)",
                    clase=ClaseHallazgo.RESULTADO_NO_SUMINISTRADO,
                    severidad=Severidad.ALTA,
                    observacion=(
                        "El expediente no aporta informe periodico de "
                        "beneficio-riesgo. El agente no infiere ausencia de senales a "
                        "partir de ausencia de informe."
                    ),
                    etiquetas=ETIQUETAS,
                ),
            ),
        )

    hallazgos: list[Hallazgo] = []

    for nombre, medicion in (
        ("Periodo de observacion del PBRER", informe.periodo_meses),
        ("Exposicion acumulada en pacientes-ano", informe.exposicion_pacientes_ano),
        ("Pacientes expuestos", informe.pacientes_expuestos),
    ):
        if medicion is None or not medicion.presente:
            hallazgos.append(
                Hallazgo(
                    parametro=nombre,
                    clase=ClaseHallazgo.RESULTADO_NO_SUMINISTRADO,
                    severidad=Severidad.ALTA,
                    observacion=(
                        f"'{nombre}' no aparece en el informe. Sin ese denominador "
                        f"ninguna tasa del PBRER es verificable."
                    ),
                    etiquetas=ETIQUETAS,
                )
            )

    for nombre, casos, declarada in (
        ("Incidencia general de eventos adversos", informe.eventos_totales,
         informe.incidencia_general_declarada),
        ("Incidencia de eventos adversos graves", informe.eventos_graves,
         informe.incidencia_graves_declarada),
    ):
        hallazgo = _incidencia_con_denominador_alterno(
            nombre, casos, informe.pacientes_expuestos,
            informe.exposicion_pacientes_ano, declarada,
        )
        if hallazgo is not None:
            hallazgos.append(hallazgo)

    if informe.muertes is not None and informe.muertes.presente:
        muertes = informe.muertes.valor.exigir()
        if muertes > 0:
            estado = (
                informe.estado_investigacion_muertes.exigir()
                if informe.estado_investigacion_muertes is not None
                and informe.estado_investigacion_muertes.presente
                else "sin estado declarado"
            )
            hallazgos.append(
                Hallazgo(
                    parametro="Muertes reportadas en el periodo",
                    clase=ClaseHallazgo.TENDENCIA_ADVERSA,
                    severidad=Severidad.CRITICA,
                    observacion=(
                        f"El informe reporta {muertes} muerte(s) con relacion "
                        f"potencial al medicamento; estado de la investigacion: "
                        f"{estado}. Mientras la investigacion siga abierta, el "
                        f"expediente no permite situar estos casos: es una "
                        f"incertidumbre, no un dato cerrado."
                    ),
                    medicion=informe.muertes,
                    etiquetas=ETIQUETAS + ("incertidumbre",),
                )
            )

    if not informe.senales:
        hallazgos.append(
            Hallazgo(
                parametro="Senales de seguridad del PBRER",
                clase=ClaseHallazgo.RESULTADO_NO_SUMINISTRADO,
                severidad=Severidad.MEDIA,
                observacion=(
                    "El informe no lista senales de seguridad. La ausencia de senales "
                    "listadas no equivale a ausencia de senales: el agente reporta que "
                    "la seccion no viene."
                ),
                etiquetas=ETIQUETAS,
            )
        )

    for senal in informe.senales:
        etiquetas = ETIQUETAS + (f"senal:{senal.identificador}",)
        if (
            senal.casos is not None
            and senal.casos.presente
            and informe.exposicion_pacientes_ano is not None
            and informe.exposicion_pacientes_ano.presente
        ):
            derivado = derivar(
                nombre=f"Tasa de '{senal.identificador}' por 1000 pacientes-ano",
                formula="casos / pacientes_ano * 1000",
                componentes=(
                    ("casos", senal.casos.valor.exigir()),
                    ("pacientes_ano", informe.exposicion_pacientes_ano.valor.exigir()),
                ),
                operacion=lambda c, p: c / p * Decimal(1000),
                unidad="por 1000 pacientes-ano",
            )
            contraste = contrastar_derivado(
                derivado,
                senal.tasa_declarada_por_1000,
                severidad_si_discrepa=Severidad.ALTA,
                etiquetas=etiquetas,
            )
            if contraste is not None:
                hallazgos.append(contraste)

        faltante = campo_ausente(
            f"Sistema u organo afectado por la senal '{senal.identificador}'",
            senal.sistema_organo,
            etiquetas,
            severidad=Severidad.MEDIA,
        )
        if faltante is not None:
            hallazgos.append(faltante)

    return ReportePBRER(informe=informe, hallazgos=tuple(hallazgos))
