"""Lectura de estudios de estabilidad formal (Modulo 3.3).

Lo que este servicio hace: contrastar cada punto de muestreo contra la
especificacion declarada, senalar el primer punto que la rebasa, describir la
deriva y avisar cuando la vida util declarada va mas alla del ultimo punto con
dato real.

Lo que NO hace: concluir que un producto es "termolabil", fijarle vida util ni
recomendar una leyenda de etiqueta. Eso es concepto tecnico y lo firma el
evaluador. El agente entrega la curva y la distancia al limite.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Sequence

from ..modelos import (
    ClaseHallazgo,
    Especificacion,
    Hallazgo,
    Medicion,
    Severidad,
    contrastar,
)
from ..valores import Dato, Traza


@dataclass(frozen=True, slots=True)
class CondicionEstabilidad:
    """Condicion bajo la que se guardaron las muestras, tal como la declara M3.3."""

    nombre: str
    temperatura: Dato[str]
    humedad_relativa: Dato[str] | None = None

    def descripcion(self) -> str:
        temperatura = self.temperatura.valor or "temperatura no declarada"
        if self.humedad_relativa is not None and self.humedad_relativa.presente:
            return f"{temperatura} / {self.humedad_relativa.valor} HR"
        return str(temperatura)

    def a_dict(self) -> dict[str, Any]:
        return {
            "nombre": self.nombre,
            "descripcion": self.descripcion(),
            "temperatura": self.temperatura.a_dict(),
            "humedad_relativa": (
                self.humedad_relativa.a_dict() if self.humedad_relativa else None
            ),
        }


@dataclass(frozen=True, slots=True)
class PuntoMuestreo:
    mes: int
    medicion: Medicion

    def a_dict(self) -> dict[str, Any]:
        return {"mes": self.mes, **self.medicion.a_dict()}


@dataclass(frozen=True, slots=True)
class EstudioEstabilidad:
    """Una condicion, un parametro seguido en el tiempo, su especificacion."""

    condicion: CondicionEstabilidad
    parametro: str
    especificacion: Especificacion | None
    puntos: tuple[PuntoMuestreo, ...]
    duracion_declarada_meses: Dato[int] | None = None

    @property
    def puntos_ordenados(self) -> tuple[PuntoMuestreo, ...]:
        return tuple(sorted(self.puntos, key=lambda p: p.mes))


@dataclass(frozen=True, slots=True)
class ReporteEstudio:
    condicion: str
    parametro: str
    puntos: tuple[PuntoMuestreo, ...]
    primer_mes_fuera: int | None
    hallazgos: tuple[Hallazgo, ...]

    def a_dict(self) -> dict[str, Any]:
        return {
            "condicion": self.condicion,
            "parametro": self.parametro,
            "puntos": [p.a_dict() for p in self.puntos],
            "primer_mes_fuera_de_especificacion": self.primer_mes_fuera,
            "hallazgos": [h.a_dict() for h in self.hallazgos],
        }


def _serie_creciente(valores: Sequence[Decimal]) -> bool:
    return len(valores) >= 3 and all(b > a for a, b in zip(valores, valores[1:]))


def _proyeccion_lineal(
    puntos: Sequence[PuntoMuestreo], limite: Decimal
) -> tuple[int, Decimal] | None:
    """Mes en que la recta por los dos ultimos puntos cruzaria el limite.

    Aritmetica de dos puntos, deliberadamente simple y reproducible. No sustituye
    el analisis de regresion de ICH Q1E; sirve para decidir si vale la pena que
    un humano mire la curva, y asi se declara en el texto del hallazgo.
    """
    if len(puntos) < 2:
        return None
    penultimo, ultimo = puntos[-2], puntos[-1]
    if not (penultimo.medicion.presente and ultimo.medicion.presente):
        return None
    meses = Decimal(ultimo.mes - penultimo.mes)
    if meses <= 0:
        return None
    v0 = penultimo.medicion.valor.exigir()
    v1 = ultimo.medicion.valor.exigir()
    pendiente = (v1 - v0) / meses
    if pendiente <= 0 or v1 >= limite:
        return None
    meses_restantes = (limite - v1) / pendiente
    return int(ultimo.mes + meses_restantes), pendiente


def evaluar_estudio(
    estudio: EstudioEstabilidad,
    severidad_si_desvia: Severidad = Severidad.ALTA,
) -> ReporteEstudio:
    """Contrasta punto por punto y describe la trayectoria."""
    puntos = estudio.puntos_ordenados
    condicion = estudio.condicion.descripcion()
    etiquetas = ("estabilidad", f"condicion:{estudio.condicion.nombre}")
    hallazgos: list[Hallazgo] = []
    primer_mes_fuera: int | None = None

    if not puntos:
        return ReporteEstudio(
            condicion=condicion,
            parametro=estudio.parametro,
            puntos=(),
            primer_mes_fuera=None,
            hallazgos=(
                Hallazgo(
                    parametro=f"{estudio.parametro} ({condicion})",
                    clase=ClaseHallazgo.RESULTADO_NO_SUMINISTRADO,
                    severidad=Severidad.ALTA,
                    observacion=(
                        f"El expediente describe la condicion {condicion} para "
                        f"'{estudio.parametro}' pero no aporta puntos de muestreo. "
                        f"Sin datos no hay lectura de estabilidad posible."
                    ),
                    etiquetas=etiquetas,
                ),
            ),
        )

    for punto in puntos:
        hallazgo = contrastar(
            punto.medicion,
            estudio.especificacion,
            severidad_si_desvia=severidad_si_desvia,
            etiquetas=etiquetas + (f"mes:{punto.mes}",),
        )
        observacion = f"Mes {punto.mes} bajo {condicion}. " + hallazgo.observacion
        hallazgos.append(
            Hallazgo(
                parametro=f"{estudio.parametro} ({condicion}, mes {punto.mes})",
                clase=hallazgo.clase,
                severidad=hallazgo.severidad,
                observacion=observacion,
                medicion=hallazgo.medicion,
                especificacion=hallazgo.especificacion,
                desvio_relativo=hallazgo.desvio_relativo,
                etiquetas=hallazgo.etiquetas,
            )
        )
        if (
            hallazgo.clase is ClaseHallazgo.FUERA_DE_ESPECIFICACION
            and primer_mes_fuera is None
        ):
            primer_mes_fuera = punto.mes

    valores = tuple(p.medicion.valor.exigir() for p in puntos if p.medicion.presente)

    if primer_mes_fuera is None and _serie_creciente(valores):
        hallazgos.append(
            Hallazgo(
                parametro=f"{estudio.parametro} ({condicion})",
                clase=ClaseHallazgo.TENDENCIA_ADVERSA,
                severidad=Severidad.MEDIA,
                observacion=(
                    f"'{estudio.parametro}' bajo {condicion}: todos los puntos caen "
                    f"dentro de la especificacion declarada pero la serie crece de "
                    f"forma monotona ({' -> '.join(str(v) for v in valores)}). No hay "
                    f"desvio; se senala la deriva para lectura del evaluador."
                ),
                etiquetas=etiquetas + ("deriva",),
            )
        )

    if (
        primer_mes_fuera is None
        and estudio.especificacion is not None
        and estudio.especificacion.maximo is not None
    ):
        proyeccion = _proyeccion_lineal(puntos, estudio.especificacion.maximo)
        declarada = (
            estudio.duracion_declarada_meses.valor
            if estudio.duracion_declarada_meses is not None
            else None
        )
        # Una recta que cruza el limite mucho despues del periodo declarado no
        # dice nada util: se descarta en vez de llenar el tablero de ruido.
        if proyeccion is not None and (
            declarada is None or proyeccion[0] <= declarada
        ):
            mes_cruce, pendiente = proyeccion
            hallazgos.append(
                Hallazgo(
                    parametro=f"{estudio.parametro} ({condicion})",
                    clase=ClaseHallazgo.TENDENCIA_ADVERSA,
                    severidad=Severidad.BAJA,
                    observacion=(
                        f"'{estudio.parametro}' bajo {condicion}: proyeccion aritmetica "
                        f"lineal entre los dos ultimos puntos (pendiente "
                        f"{pendiente.quantize(Decimal('0.0001'))} por mes) alcanzaria el "
                        f"limite {estudio.especificacion.descripcion()} hacia el mes "
                        f"{mes_cruce}. Es una recta de dos puntos, no un analisis de "
                        f"regresion ICH Q1E; sirve solo para priorizar la lectura."
                    ),
                    etiquetas=etiquetas + ("proyeccion",),
                )
            )

    if estudio.duracion_declarada_meses is not None and estudio.duracion_declarada_meses.presente:
        declarada = estudio.duracion_declarada_meses.exigir()
        ultimo_mes = puntos[-1].mes
        if declarada > ultimo_mes:
            hallazgos.append(
                Hallazgo(
                    parametro=f"Cobertura temporal del estudio ({condicion})",
                    clase=ClaseHallazgo.RESULTADO_NO_SUMINISTRADO,
                    severidad=Severidad.ALTA,
                    observacion=(
                        f"La duracion declarada del estudio bajo {condicion} es "
                        f"{declarada} meses, pero el ultimo punto de muestreo con dato "
                        f"es el mes {ultimo_mes}. Los meses {ultimo_mes + 1} a "
                        f"{declarada} no estan respaldados por resultados en el "
                        f"expediente."
                    ),
                    etiquetas=etiquetas + ("cobertura",),
                    trazas_adicionales=(
                        Traza(descripcion=f"Ultimo punto con dato: mes {ultimo_mes}"),
                    ),
                )
            )

    return ReporteEstudio(
        condicion=condicion,
        parametro=estudio.parametro,
        puntos=puntos,
        primer_mes_fuera=primer_mes_fuera,
        hallazgos=tuple(hallazgos),
    )
