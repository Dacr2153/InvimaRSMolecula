"""Contraste de resultados de liberacion entre lotes consecutivos.

Dos preguntas distintas, que el spec de origen mezclaba en una sola casilla:

1. Cada lote por separado, cae dentro de su especificacion declarada?
   Eso es contraste contra el expediente y produce Hallazgos verificables.
2. Los lotes se parecen entre si?
   Eso es dispersion. El umbral de CV NO sale del expediente: es un criterio
   operativo del agente para decidir a que le pide una mirada humana. Va
   marcado como tal en la observacion, y el Dato correspondiente nace con
   origen RECOMENDACION, no EXTRAIDO.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Any, Mapping, Sequence

from ..errores import SerieInsuficienteError
from ..modelos import (
    ClaseHallazgo,
    Especificacion,
    Hallazgo,
    Medicion,
    Severidad,
    contrastar,
)
from ..valores import Dato
from .estadistica import DOS_DECIMALES, ResumenEstadistico, resumir

#: Criterio operativo del agente, no especificacion normativa. Por encima de
#: este coeficiente de variacion el hallazgo se eleva para lectura humana.
UMBRAL_CV_PORCENTAJE = Decimal("10")

#: Minimo de lotes consecutivos que se esperan para hablar de consistencia.
LOTES_MINIMOS = 3


@dataclass(frozen=True, slots=True)
class Lote:
    """Resultados de liberacion de un lote comercial."""

    identificacion: str
    fecha_fabricacion: date | None
    mediciones: tuple[Medicion, ...]

    def medicion_de(self, parametro: str) -> Medicion | None:
        for m in self.mediciones:
            if m.parametro == parametro:
                return m
        return None


@dataclass(frozen=True, slots=True)
class SerieParametro:
    """Un parametro seguido a lo largo de varios lotes."""

    parametro: str
    unidad: str
    lotes: tuple[str, ...]
    valores: tuple[Decimal, ...]
    lotes_sin_resultado: tuple[str, ...]
    resumen: ResumenEstadistico | None

    def a_dict(self) -> dict[str, Any]:
        return {
            "parametro": self.parametro,
            "unidad": self.unidad or None,
            "lotes": list(self.lotes),
            "valores": [float(v) for v in self.valores],
            "lotes_sin_resultado": list(self.lotes_sin_resultado),
            "estadistica": self.resumen.a_dict() if self.resumen else None,
        }


@dataclass(frozen=True, slots=True)
class ReporteConsistencia:
    lotes_evaluados: tuple[str, ...]
    series: tuple[SerieParametro, ...]
    hallazgos: tuple[Hallazgo, ...]
    dispersion_dentro_del_criterio: Dato[bool]

    def a_dict(self) -> dict[str, Any]:
        return {
            "lotes_evaluados": list(self.lotes_evaluados),
            "series": [s.a_dict() for s in self.series],
            "hallazgos": [h.a_dict() for h in self.hallazgos],
            "dispersion_dentro_del_criterio_operativo": (
                self.dispersion_dentro_del_criterio.a_dict()
            ),
            "criterio_operativo_cv_porcentaje": float(UMBRAL_CV_PORCENTAJE),
        }


def construir_serie(lotes: Sequence[Lote], parametro: str) -> SerieParametro:
    """Recoge un parametro a lo largo de los lotes, sin rellenar los ausentes."""
    identificaciones: list[str] = []
    valores: list[Decimal] = []
    ausentes: list[str] = []
    unidad = ""
    for lote in lotes:
        medicion = lote.medicion_de(parametro)
        if medicion is None or not medicion.presente:
            ausentes.append(lote.identificacion)
            continue
        unidad = unidad or medicion.unidad
        identificaciones.append(lote.identificacion)
        valores.append(medicion.valor.exigir())
    try:
        resumen = resumir(valores) if len(valores) >= 2 else None
    except SerieInsuficienteError:
        resumen = None
    return SerieParametro(
        parametro=parametro,
        unidad=unidad,
        lotes=tuple(identificaciones),
        valores=tuple(valores),
        lotes_sin_resultado=tuple(ausentes),
        resumen=resumen,
    )


def _hallazgo_dispersion(serie: SerieParametro) -> Hallazgo | None:
    """Traduce el coeficiente de variacion a un hallazgo, o a nada."""
    if serie.resumen is None or serie.resumen.coeficiente_variacion is None:
        return None
    cv = serie.resumen.coeficiente_variacion
    dentro = cv <= UMBRAL_CV_PORCENTAJE
    cv_texto = cv.quantize(DOS_DECIMALES)
    if dentro:
        return Hallazgo(
            parametro=f"{serie.parametro} (dispersion entre lotes)",
            clase=ClaseHallazgo.DENTRO_DE_ESPECIFICACION,
            severidad=Severidad.INFORMATIVA,
            observacion=(
                f"'{serie.parametro}': coeficiente de variacion {cv_texto}% sobre "
                f"{serie.resumen.n} lotes ({', '.join(serie.lotes)}), por debajo del "
                f"criterio operativo del agente de {UMBRAL_CV_PORCENTAJE}%. El "
                f"criterio de dispersion no proviene del expediente."
            ),
            etiquetas=("consistencia_lotes", "dispersion"),
        )
    return Hallazgo(
        parametro=f"{serie.parametro} (dispersion entre lotes)",
        clase=ClaseHallazgo.TENDENCIA_ADVERSA,
        severidad=Severidad.MEDIA,
        observacion=(
            f"'{serie.parametro}': coeficiente de variacion {cv_texto}% sobre "
            f"{serie.resumen.n} lotes ({', '.join(serie.lotes)}), por encima del "
            f"criterio operativo del agente de {UMBRAL_CV_PORCENTAJE}%. Los valores "
            f"observados van de {serie.resumen.minimo} a {serie.resumen.maximo}. "
            f"El criterio de dispersion no proviene del expediente; el evaluador "
            f"decide si la variabilidad es admisible para este proceso."
        ),
        etiquetas=("consistencia_lotes", "dispersion"),
    )


def evaluar_consistencia(
    lotes: Sequence[Lote],
    especificaciones: Mapping[str, Especificacion],
    severidades: Mapping[str, Severidad] | None = None,
) -> ReporteConsistencia:
    """Contrasta cada lote contra especificacion y describe la dispersion.

    `especificaciones` debe venir del expediente. Un parametro sin especificacion
    produce un hallazgo ESPECIFICACION_NO_DECLARADA, no un silencio.
    """
    severidades = severidades or {}
    hallazgos: list[Hallazgo] = []
    identificaciones = tuple(lote.identificacion for lote in lotes)

    if len(lotes) < LOTES_MINIMOS:
        hallazgos.append(
            Hallazgo(
                parametro="Serie de lotes comerciales",
                clase=ClaseHallazgo.RESULTADO_NO_SUMINISTRADO,
                severidad=Severidad.ALTA,
                observacion=(
                    f"El expediente aporta {len(lotes)} lote(s) "
                    f"({', '.join(identificaciones) or 'ninguno'}); se esperan al "
                    f"menos {LOTES_MINIMOS} lotes consecutivos para observar "
                    f"consistencia de proceso. No se extrapola desde los aportados."
                ),
                etiquetas=("consistencia_lotes",),
            )
        )

    parametros: list[str] = []
    for lote in lotes:
        for medicion in lote.mediciones:
            if medicion.parametro not in parametros:
                parametros.append(medicion.parametro)

    series: list[SerieParametro] = []
    for parametro in parametros:
        especificacion = especificaciones.get(parametro)
        severidad = severidades.get(parametro, Severidad.ALTA)
        for lote in lotes:
            medicion = lote.medicion_de(parametro)
            if medicion is None:
                continue
            hallazgo = contrastar(
                medicion,
                especificacion,
                severidad_si_desvia=severidad,
                etiquetas=("consistencia_lotes", f"lote:{lote.identificacion}"),
            )
            # El parametro nombra el lote: tres hallazgos identicos en el tablero
            # no dejan ver a cual de los tres lotes hay que ir a mirar.
            hallazgos.append(
                replace(
                    hallazgo,
                    parametro=f"{parametro} (lote {lote.identificacion})",
                )
            )
        serie = construir_serie(lotes, parametro)
        series.append(serie)
        dispersion = _hallazgo_dispersion(serie)
        if dispersion is not None:
            hallazgos.append(dispersion)

    excedidos = [
        s.parametro
        for s in series
        if s.resumen is not None
        and s.resumen.coeficiente_variacion is not None
        and s.resumen.coeficiente_variacion > UMBRAL_CV_PORCENTAJE
    ]
    dispersion_ok = Dato.recomendado(
        not excedidos,
        razon=(
            "todos los parametros seguidos quedan bajo el criterio operativo de "
            f"CV {UMBRAL_CV_PORCENTAJE}%"
            if not excedidos
            else "superan el criterio operativo de CV: " + ", ".join(excedidos)
        ),
    )

    return ReporteConsistencia(
        lotes_evaluados=identificaciones,
        series=tuple(series),
        hallazgos=tuple(hallazgos),
        dispersion_dentro_del_criterio=dispersion_ok,
    )
