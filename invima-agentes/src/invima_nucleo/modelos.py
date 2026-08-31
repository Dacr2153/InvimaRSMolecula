"""Modelo de una auditoria documental: medicion, especificacion, hallazgo.

Una regla gobierna todo este archivo: la especificacion contra la que se compara
un resultado NO la pone el agente. Sale del expediente o de una fuente normativa
citable, y viaja como Dato con su traza. Si el expediente no la declara, el
resultado es "no verificable" -- nunca "conforme".

Ningun tipo de aqui produce las palabras aprobar, rechazar o cumple. El agente
describe la distancia entre lo observado y lo declarado; la lectura juridica de
esa distancia es del evaluador.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any

from .errores import EspecificacionInvalidaError
from .valores import Dato, OrigenDato, Traza


class Severidad(StrEnum):
    """Cuanta atencion humana reclama un hallazgo. No es un veredicto."""

    CRITICA = "CRITICA"
    ALTA = "ALTA"
    MEDIA = "MEDIA"
    BAJA = "BAJA"
    INFORMATIVA = "INFORMATIVA"


ORDEN_SEVERIDAD: dict[Severidad, int] = {
    Severidad.CRITICA: 0,
    Severidad.ALTA: 1,
    Severidad.MEDIA: 2,
    Severidad.BAJA: 3,
    Severidad.INFORMATIVA: 4,
}


class ClaseHallazgo(StrEnum):
    """Resultado del contraste entre una medicion y su especificacion."""

    DENTRO_DE_ESPECIFICACION = "DENTRO_DE_ESPECIFICACION"
    FUERA_DE_ESPECIFICACION = "FUERA_DE_ESPECIFICACION"
    ESPECIFICACION_NO_DECLARADA = "ESPECIFICACION_NO_DECLARADA"
    """Hay resultado pero el expediente no dice contra que limite se juzga."""

    RESULTADO_NO_SUMINISTRADO = "RESULTADO_NO_SUMINISTRADO"
    """Hay especificacion pero el expediente no reporta el resultado."""

    NO_COMPARABLE = "NO_COMPARABLE"
    """Unidades distintas o texto no interpretable. Se marca, no se convierte."""

    TENDENCIA_ADVERSA = "TENDENCIA_ADVERSA"
    """Puntos individuales dentro de limite pero con deriva sostenida."""

    DISCREPANCIA_ARITMETICA = "DISCREPANCIA_ARITMETICA"
    """El valor declarado no se reproduce a partir de sus propios componentes."""


@dataclass(frozen=True, slots=True)
class Especificacion:
    """Limite declarado para un parametro, con la fuente que lo declara.

    Cuantitativa (minimo / maximo) o cualitativa (valor_esperado). Nunca ambas
    vacias: eso seria simular un contraste inexistente.
    """

    parametro: str
    unidad: str = ""
    minimo: Decimal | None = None
    maximo: Decimal | None = None
    valor_esperado: str = ""
    fuente: Traza | None = None

    def __post_init__(self) -> None:
        sin_limites = self.minimo is None and self.maximo is None
        if sin_limites and not self.valor_esperado.strip():
            raise EspecificacionInvalidaError(
                f"La especificacion de '{self.parametro}' no declara limites ni "
                f"valor esperado; no hay contra que contrastar"
            )

    @property
    def es_cuantitativa(self) -> bool:
        return self.minimo is not None or self.maximo is not None

    def contiene(self, valor: Decimal) -> bool:
        if self.minimo is not None and valor < self.minimo:
            return False
        if self.maximo is not None and valor > self.maximo:
            return False
        return True

    def desvio_relativo(self, valor: Decimal) -> Decimal | None:
        """Porcentaje en que el valor rebasa el limite mas cercano que viola.

        Devuelve None si el valor esta dentro, o si el limite violado es cero
        (division indefinida: se reporta el hallazgo sin porcentaje).
        """
        if self.contiene(valor):
            return None
        if self.maximo is not None and valor > self.maximo:
            if self.maximo == 0:
                return None
            return (valor - self.maximo) / self.maximo * Decimal(100)
        if self.minimo is not None and valor < self.minimo:
            if self.minimo == 0:
                return None
            return (self.minimo - valor) / self.minimo * Decimal(100)
        return None

    def descripcion(self) -> str:
        if not self.es_cuantitativa:
            return self.valor_esperado
        unidad = f" {self.unidad}" if self.unidad else ""
        if self.minimo is not None and self.maximo is not None:
            return f"{self.minimo}-{self.maximo}{unidad}"
        if self.maximo is not None:
            return f"<= {self.maximo}{unidad}"
        return f">= {self.minimo}{unidad}"

    def a_dict(self) -> dict[str, Any]:
        return {
            "parametro": self.parametro,
            "descripcion": self.descripcion(),
            "unidad": self.unidad or None,
            "minimo": float(self.minimo) if self.minimo is not None else None,
            "maximo": float(self.maximo) if self.maximo is not None else None,
            "valor_esperado": self.valor_esperado or None,
            "fuente": self.fuente.a_dict() if self.fuente else None,
        }


@dataclass(frozen=True, slots=True)
class Medicion:
    """Un resultado analitico leido del expediente, con su unidad y su folio.

    El valor admite texto porque no todo resultado de calidad es un numero: un
    ensayo de lixiviables reporta "No detectados", y forzarlo a Decimal obligaria
    a codificarlo, que es una forma de interpretarlo.
    """

    parametro: str
    valor: Dato[Decimal | str]
    unidad: str = ""

    @property
    def presente(self) -> bool:
        return self.valor.presente

    def a_dict(self) -> dict[str, Any]:
        return {
            "parametro": self.parametro,
            "unidad": self.unidad or None,
            **self.valor.a_dict(),
        }


@dataclass(frozen=True, slots=True)
class Hallazgo:
    """Una observacion auditable: que se midio, contra que, y a que distancia.

    `observacion` se compone de forma determinista a partir de los campos, no la
    redacta un modelo: dos corridas sobre el mismo expediente producen el mismo
    texto, palabra por palabra.
    """

    parametro: str
    clase: ClaseHallazgo
    severidad: Severidad
    observacion: str
    medicion: Medicion | None = None
    especificacion: Especificacion | None = None
    desvio_relativo: Decimal | None = None
    etiquetas: tuple[str, ...] = ()
    trazas_adicionales: tuple[Traza, ...] = field(default_factory=tuple)

    @property
    def exige_lectura_humana(self) -> bool:
        return self.severidad in (Severidad.CRITICA, Severidad.ALTA)

    def a_dict(self) -> dict[str, Any]:
        return {
            "parametro": self.parametro,
            "clase": str(self.clase),
            "severidad": str(self.severidad),
            "observacion": self.observacion,
            "medicion": self.medicion.a_dict() if self.medicion else None,
            "especificacion": (
                self.especificacion.a_dict() if self.especificacion else None
            ),
            "desvio_relativo_porcentaje": (
                float(round(self.desvio_relativo, 2))
                if self.desvio_relativo is not None
                else None
            ),
            "etiquetas": list(self.etiquetas),
            "trazabilidad_adicional": [t.a_dict() for t in self.trazas_adicionales],
        }


def _texto_medicion(medicion: Medicion) -> str:
    unidad = f" {medicion.unidad}" if medicion.unidad else ""
    return f"{medicion.valor.exigir()}{unidad}"


def contrastar(
    medicion: Medicion,
    especificacion: Especificacion | None,
    severidad_si_desvia: Severidad = Severidad.ALTA,
    etiquetas: tuple[str, ...] = (),
) -> Hallazgo:
    """Contrasta un resultado contra su especificacion y devuelve un Hallazgo.

    La severidad de un desvio la declara quien llama, porque depende del
    parametro: un LRV viral insuficiente y una concentracion de proteina en el
    borde del rango no pesan igual. Aqui no se inventa esa jerarquia.
    """
    if especificacion is None:
        return Hallazgo(
            parametro=medicion.parametro,
            clase=ClaseHallazgo.ESPECIFICACION_NO_DECLARADA,
            severidad=Severidad.MEDIA,
            observacion=(
                f"El expediente reporta un resultado para '{medicion.parametro}' "
                f"pero no declara la especificacion aplicable. El resultado no es "
                f"verificable contra un limite; se requiere que el solicitante la "
                f"declare o que el evaluador la fije desde la norma aplicable."
            ),
            medicion=medicion,
            etiquetas=etiquetas,
        )

    if not medicion.presente:
        return Hallazgo(
            parametro=medicion.parametro,
            clase=ClaseHallazgo.RESULTADO_NO_SUMINISTRADO,
            severidad=Severidad.ALTA,
            observacion=(
                f"El expediente declara la especificacion "
                f"'{especificacion.descripcion()}' para '{medicion.parametro}' pero "
                f"no reporta resultado. No se infiere ningun valor."
            ),
            medicion=medicion,
            especificacion=especificacion,
            etiquetas=etiquetas,
        )

    if not especificacion.es_cuantitativa:
        observado = str(medicion.valor.exigir())
        coincide = observado.strip().casefold() == especificacion.valor_esperado.strip().casefold()
        return Hallazgo(
            parametro=medicion.parametro,
            clase=(
                ClaseHallazgo.DENTRO_DE_ESPECIFICACION
                if coincide
                else ClaseHallazgo.FUERA_DE_ESPECIFICACION
            ),
            severidad=Severidad.INFORMATIVA if coincide else severidad_si_desvia,
            observacion=(
                f"'{medicion.parametro}': el expediente reporta '{observado}' y la "
                f"especificacion declarada es '{especificacion.valor_esperado}'."
                + ("" if coincide else " Los valores difieren.")
            ),
            medicion=medicion,
            especificacion=especificacion,
            etiquetas=etiquetas,
        )

    if especificacion.unidad and medicion.unidad and especificacion.unidad != medicion.unidad:
        return Hallazgo(
            parametro=medicion.parametro,
            clase=ClaseHallazgo.NO_COMPARABLE,
            severidad=Severidad.MEDIA,
            observacion=(
                f"'{medicion.parametro}': el resultado esta en {medicion.unidad} y la "
                f"especificacion en {especificacion.unidad}. El agente no convierte "
                f"unidades; el contraste queda para el evaluador."
            ),
            medicion=medicion,
            especificacion=especificacion,
            etiquetas=etiquetas,
        )

    valor = medicion.valor.exigir()
    dentro = especificacion.contiene(valor)
    desvio = especificacion.desvio_relativo(valor)
    if dentro:
        observacion = (
            f"'{medicion.parametro}': resultado {_texto_medicion(medicion)} dentro de "
            f"la especificacion declarada {especificacion.descripcion()}."
        )
    else:
        exceso = f" ({desvio.quantize(Decimal('0.01'))}% de desvio)" if desvio is not None else ""
        observacion = (
            f"'{medicion.parametro}': resultado {_texto_medicion(medicion)} fuera de "
            f"la especificacion declarada {especificacion.descripcion()}{exceso}."
        )
    return Hallazgo(
        parametro=medicion.parametro,
        clase=(
            ClaseHallazgo.DENTRO_DE_ESPECIFICACION
            if dentro
            else ClaseHallazgo.FUERA_DE_ESPECIFICACION
        ),
        severidad=Severidad.INFORMATIVA if dentro else severidad_si_desvia,
        observacion=observacion,
        medicion=medicion,
        especificacion=especificacion,
        desvio_relativo=desvio,
        etiquetas=etiquetas,
    )


def sin_especificacion(parametro: str, motivo: str) -> Hallazgo:
    """Hallazgo para un parametro que el expediente no aborda en absoluto."""
    return Hallazgo(
        parametro=parametro,
        clase=ClaseHallazgo.RESULTADO_NO_SUMINISTRADO,
        severidad=Severidad.ALTA,
        observacion=motivo,
        medicion=Medicion(
            parametro=parametro,
            valor=Dato(valor=None, origen=OrigenDato.NO_SUMINISTRADO,
                       traza=Traza(descripcion=f"No suministrado en el expediente: {parametro}")),
        ),
    )
