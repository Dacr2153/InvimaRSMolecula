"""Auditoria de los atributos criticos de la sustancia activa (M3.2.S).

Contra la tentacion de cablear valores: aqui no hay ninguna constante del tipo
"peso molecular = 148210 Da" ni "viabilidad minima = 92%". Esos numeros son
propios de cada molecula y salen del expediente o de la norma citada. Cablearlos
convertiria al agente en un validador de un unico producto sintetico.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Mapping

from ..modelos import ClaseHallazgo, Especificacion, Hallazgo, Medicion, Severidad
from ..valores import Dato
from .contraste import ParametroAuditado, auditar, campo_ausente

#: Tolerancia con que se acepta que un perfil de glicoformas cierre en 100%.
#: Criterio operativo del agente: absorbe el redondeo de los porcentajes
#: reportados, no es una especificacion normativa.
TOLERANCIA_CIERRE_PERFIL = Decimal("2.0")


@dataclass(frozen=True, slots=True)
class SustanciaActiva:
    """Lo que M3.2.S declara sobre la molecula y su sistema productor."""

    linea_celular: Dato[str]
    sistema_expresion: Dato[str]
    viabilidad_banco_maestro: Medicion | None = None
    viabilidad_banco_trabajo: Medicion | None = None
    peso_molecular: Medicion | None = None
    perfil_glicosilacion: tuple[Medicion, ...] = field(default_factory=tuple)

    def a_dict(self) -> dict[str, Any]:
        return {
            "linea_celular": self.linea_celular.a_dict(),
            "sistema_expresion": self.sistema_expresion.a_dict(),
            "viabilidad_banco_maestro": (
                self.viabilidad_banco_maestro.a_dict()
                if self.viabilidad_banco_maestro
                else None
            ),
            "viabilidad_banco_trabajo": (
                self.viabilidad_banco_trabajo.a_dict()
                if self.viabilidad_banco_trabajo
                else None
            ),
            "peso_molecular": (
                self.peso_molecular.a_dict() if self.peso_molecular else None
            ),
            "perfil_glicosilacion": [m.a_dict() for m in self.perfil_glicosilacion],
        }


ETIQUETAS = ("sustancia_activa", "M3.2.S")


def _cierre_del_perfil(perfil: tuple[Medicion, ...]) -> Hallazgo | None:
    """Verifica que las glicoformas declaradas sumen aproximadamente 100%.

    Un perfil que suma 78% no esta "fuera de rango": esta incompleto, y decir
    que las formas declaradas caen en rango seria una lectura tranquilizadora de
    un expediente al que le faltan formas.
    """
    presentes = [m for m in perfil if m.presente]
    if len(presentes) < 2:
        return None
    total = sum((m.valor.exigir() for m in presentes), Decimal(0))
    distancia = abs(total - Decimal(100))
    if distancia <= TOLERANCIA_CIERRE_PERFIL:
        return None
    return Hallazgo(
        parametro="Cierre del perfil de glicosilacion",
        clase=ClaseHallazgo.TENDENCIA_ADVERSA,
        severidad=Severidad.MEDIA,
        observacion=(
            f"Las {len(presentes)} glicoformas declaradas suman "
            f"{total.quantize(Decimal('0.01'))}%, a "
            f"{distancia.quantize(Decimal('0.01'))} puntos del 100%. El perfil "
            f"reportado no cierra: o faltan formas por declarar o alguno de los "
            f"porcentajes esta mal transcrito. Contrastar cada forma por separado "
            f"sobre un perfil incompleto daria una lectura enganosa."
        ),
        etiquetas=ETIQUETAS + ("perfil_glicosilacion",),
    )


@dataclass(frozen=True, slots=True)
class ReporteSustanciaActiva:
    sustancia: SustanciaActiva
    hallazgos: tuple[Hallazgo, ...]

    def a_dict(self) -> dict[str, Any]:
        return {
            "sustancia_activa": self.sustancia.a_dict(),
            "hallazgos": [h.a_dict() for h in self.hallazgos],
        }


def auditar_sustancia_activa(
    sustancia: SustanciaActiva,
    especificaciones: Mapping[str, Especificacion],
    severidades: Mapping[str, Severidad] | None = None,
) -> ReporteSustanciaActiva:
    """Contrasta los atributos declarados contra las especificaciones del dossier."""
    severidades = severidades or {}
    hallazgos: list[Hallazgo] = []

    for nombre, dato in (
        ("Linea celular", sustancia.linea_celular),
        ("Sistema de expresion", sustancia.sistema_expresion),
    ):
        faltante = campo_ausente(nombre, dato, etiquetas=ETIQUETAS)
        if faltante is not None:
            hallazgos.append(faltante)

    mediciones = [
        m
        for m in (
            sustancia.viabilidad_banco_maestro,
            sustancia.viabilidad_banco_trabajo,
            sustancia.peso_molecular,
        )
        if m is not None
    ]
    mediciones.extend(sustancia.perfil_glicosilacion)

    parametros = [
        ParametroAuditado(
            medicion=m,
            especificacion=especificaciones.get(m.parametro),
            severidad_si_desvia=severidades.get(m.parametro, Severidad.ALTA),
        )
        for m in mediciones
    ]
    hallazgos.extend(auditar(parametros, etiquetas=ETIQUETAS))

    cierre = _cierre_del_perfil(sustancia.perfil_glicosilacion)
    if cierre is not None:
        hallazgos.append(cierre)

    return ReporteSustanciaActiva(sustancia=sustancia, hallazgos=tuple(hallazgos))
