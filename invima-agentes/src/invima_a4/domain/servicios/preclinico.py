"""Auditoria de la evidencia no clinica (Modulo 4).

Farmacocinetica en animal, toxicologia de dosis repetidas y toxicologia
reproductiva. Tres reglas gobiernan el archivo:

1. El agente no asigna categorias de riesgo en embarazo. La categoria la
   declara el expediente; si no esta, se reporta ausente. Asignarla es un
   juicio toxicologico con consecuencias de etiqueta.
2. Un hallazgo sin reversibilidad declarada no es interpretable, y eso se dice
   en vez de leerlo como benigno.
3. El margen de seguridad se recalcula a partir del NOAEL y de la dosis clinica
   propuesta. Si el expediente declara otro, se reportan los dos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Mapping

from ..modelos import (
    ClaseHallazgo,
    Especificacion,
    Hallazgo,
    Medicion,
    Severidad,
    contrastar_derivado,
    derivar,
)
from ..valores import Dato
from invima_nucleo.contraste import ParametroAuditado, auditar, campo_ausente

ETIQUETAS_PK = ("no_clinico", "farmacocinetica", "M4.2")
ETIQUETAS_TOX = ("no_clinico", "toxicologia", "M4.3")
ETIQUETAS_REPRO = ("no_clinico", "toxicologia_reproductiva", "M4.4")

#: Fraccion de dosis materna que llega al feto por encima de la cual el agente
#: eleva el hallazgo para lectura humana. Criterio operativo del agente,
#: declarado como tal en el texto: no proviene del expediente ni de una norma
#: citada en el.
UMBRAL_TRANSFERENCIA_PLACENTARIA = Decimal("30")


@dataclass(frozen=True, slots=True)
class EstudioFarmacocinetico:
    estudio_id: Dato[str]
    especie: Dato[str]
    ruta_administracion: Dato[str]
    dosis: Medicion | None = None
    parametros: tuple[Medicion, ...] = field(default_factory=tuple)

    def a_dict(self) -> dict[str, Any]:
        return {
            "estudio_id": self.estudio_id.a_dict(),
            "especie": self.especie.a_dict(),
            "ruta_administracion": self.ruta_administracion.a_dict(),
            "dosis": self.dosis.a_dict() if self.dosis else None,
            "parametros": [m.a_dict() for m in self.parametros],
        }


@dataclass(frozen=True, slots=True)
class EstudioToxicologia:
    estudio_id: Dato[str]
    especie: Dato[str]
    duracion_semanas: Medicion | None = None
    noael: Medicion | None = None
    loael: Medicion | None = None
    organo_blanco: Dato[str] | None = None
    hallazgos_cuantificados: tuple[Medicion, ...] = field(default_factory=tuple)
    reversibilidad: Dato[str] | None = None
    dosis_clinica_equivalente: Medicion | None = None
    margen_seguridad_declarado: Dato[Decimal] | None = None

    def a_dict(self) -> dict[str, Any]:
        return {
            "estudio_id": self.estudio_id.a_dict(),
            "especie": self.especie.a_dict(),
            "duracion_semanas": (
                self.duracion_semanas.a_dict() if self.duracion_semanas else None
            ),
            "noael": self.noael.a_dict() if self.noael else None,
            "loael": self.loael.a_dict() if self.loael else None,
            "organo_blanco": self.organo_blanco.a_dict() if self.organo_blanco else None,
            "hallazgos_cuantificados": [
                m.a_dict() for m in self.hallazgos_cuantificados
            ],
            "reversibilidad": (
                self.reversibilidad.a_dict() if self.reversibilidad else None
            ),
            "dosis_clinica_equivalente": (
                self.dosis_clinica_equivalente.a_dict()
                if self.dosis_clinica_equivalente
                else None
            ),
            "margen_seguridad_declarado": (
                self.margen_seguridad_declarado.a_dict()
                if self.margen_seguridad_declarado
                else None
            ),
        }


@dataclass(frozen=True, slots=True)
class Malformacion:
    tipo: Dato[str]
    descripcion: Dato[str] | None = None
    frecuencia: Medicion | None = None

    def a_dict(self) -> dict[str, Any]:
        return {
            "tipo": self.tipo.a_dict(),
            "descripcion": self.descripcion.a_dict() if self.descripcion else None,
            "frecuencia": self.frecuencia.a_dict() if self.frecuencia else None,
        }


@dataclass(frozen=True, slots=True)
class EstudioReproductivo:
    estudio_id: Dato[str]
    modelo: Dato[str]
    periodo_exposicion: Dato[str] | None = None
    dosis_materna: Medicion | None = None
    abortos_espontaneos: Dato[str] | None = None
    transferencia_placentaria: Medicion | None = None
    malformaciones: tuple[Malformacion, ...] = field(default_factory=tuple)
    categoria_embarazo_declarada: Dato[str] | None = None
    medida_mitigacion_declarada: Dato[str] | None = None

    def a_dict(self) -> dict[str, Any]:
        return {
            "estudio_id": self.estudio_id.a_dict(),
            "modelo": self.modelo.a_dict(),
            "periodo_exposicion": (
                self.periodo_exposicion.a_dict() if self.periodo_exposicion else None
            ),
            "dosis_materna": self.dosis_materna.a_dict() if self.dosis_materna else None,
            "abortos_espontaneos": (
                self.abortos_espontaneos.a_dict() if self.abortos_espontaneos else None
            ),
            "transferencia_placentaria": (
                self.transferencia_placentaria.a_dict()
                if self.transferencia_placentaria
                else None
            ),
            "malformaciones": [m.a_dict() for m in self.malformaciones],
            "categoria_embarazo_declarada": (
                self.categoria_embarazo_declarada.a_dict()
                if self.categoria_embarazo_declarada
                else None
            ),
            "medida_mitigacion_declarada": (
                self.medida_mitigacion_declarada.a_dict()
                if self.medida_mitigacion_declarada
                else None
            ),
        }


@dataclass(frozen=True, slots=True)
class ReporteNoClinico:
    farmacocinetica: EstudioFarmacocinetico | None
    toxicologia: tuple[EstudioToxicologia, ...]
    reproductiva: EstudioReproductivo | None
    hallazgos: tuple[Hallazgo, ...]

    def a_dict(self) -> dict[str, Any]:
        return {
            "farmacocinetica": (
                self.farmacocinetica.a_dict() if self.farmacocinetica else None
            ),
            "toxicologia_dosis_repetidas": [e.a_dict() for e in self.toxicologia],
            "toxicologia_reproductiva": (
                self.reproductiva.a_dict() if self.reproductiva else None
            ),
            "hallazgos": [h.a_dict() for h in self.hallazgos],
        }


def _auditar_mediciones(
    mediciones: tuple[Medicion, ...],
    especificaciones: Mapping[str, Especificacion],
    etiquetas: tuple[str, ...],
    contexto: str,
    severidad_si_desvia: Severidad,
) -> list[Hallazgo]:
    """Contrasta lo que tiene criterio declarado; lo demas lo transcribe.

    Un parametro de farmacocinetica no se aprueba ni se reprueba: describe la
    exposicion. Tratar cada uno como si le faltara una especificacion llenaria
    el tablero de hallazgos que no son hallazgos. Los parametros sin criterio se
    reportan juntos, en una sola linea, para que se vea que se leyeron.
    """
    con_criterio = [m for m in mediciones if m.parametro in especificaciones]
    sin_criterio = [m for m in mediciones if m.parametro not in especificaciones]
    hallazgos = list(
        auditar(
            [
                ParametroAuditado(
                    medicion=m,
                    especificacion=especificaciones[m.parametro],
                    severidad_si_desvia=severidad_si_desvia,
                )
                for m in con_criterio
            ],
            etiquetas=etiquetas,
        )
    )
    if sin_criterio:
        nombres = ", ".join(m.parametro for m in sin_criterio)
        hallazgos.append(
            Hallazgo(
                parametro=f"Parametros descriptivos de {contexto}",
                clase=ClaseHallazgo.DENTRO_DE_ESPECIFICACION,
                severidad=Severidad.INFORMATIVA,
                observacion=(
                    f"Se leyeron {len(sin_criterio)} parametro(s) de {contexto} que el "
                    f"expediente reporta sin criterio de aceptacion declarado "
                    f"({nombres}). Se transcriben con su folio para lectura del "
                    f"evaluador; no se contrastan contra ningun limite porque el "
                    f"expediente no lo fija."
                ),
                etiquetas=etiquetas + ("descriptivo",),
            )
        )
    return hallazgos


def _auditar_pk(
    estudio: EstudioFarmacocinetico | None,
    especificaciones: Mapping[str, Especificacion],
) -> list[Hallazgo]:
    if estudio is None:
        return [
            Hallazgo(
                parametro="Farmacocinetica no clinica",
                clase=ClaseHallazgo.RESULTADO_NO_SUMINISTRADO,
                severidad=Severidad.ALTA,
                observacion=(
                    "El expediente no aporta estudio de farmacocinetica en animal. "
                    "Sin parametros de exposicion no hay como relacionar la dosis "
                    "ensayada en toxicologia con la dosis propuesta en clinica."
                ),
                etiquetas=ETIQUETAS_PK,
            )
        ]
    hallazgos: list[Hallazgo] = []
    for nombre, dato in (
        ("Especie del estudio de farmacocinetica", estudio.especie),
        ("Ruta de administracion", estudio.ruta_administracion),
        ("Identificacion del estudio de farmacocinetica", estudio.estudio_id),
    ):
        faltante = campo_ausente(nombre, dato, ETIQUETAS_PK)
        if faltante is not None:
            hallazgos.append(faltante)
    hallazgos.extend(
        _auditar_mediciones(
            estudio.parametros,
            especificaciones,
            ETIQUETAS_PK,
            "farmacocinetica no clinica",
            Severidad.MEDIA,
        )
    )
    return hallazgos


def _auditar_toxicologia(
    estudio: EstudioToxicologia,
    especificaciones: Mapping[str, Especificacion],
) -> list[Hallazgo]:
    etiquetas = ETIQUETAS_TOX + (f"estudio:{estudio.estudio_id.valor or 'sin id'}",)
    hallazgos: list[Hallazgo] = []

    for nombre, dato in (
        ("Identificacion del estudio de toxicologia", estudio.estudio_id),
        ("Especie del estudio de toxicologia", estudio.especie),
    ):
        faltante = campo_ausente(nombre, dato, etiquetas)
        if faltante is not None:
            hallazgos.append(faltante)

    hallazgos.extend(
        _auditar_mediciones(
            estudio.hallazgos_cuantificados,
            especificaciones,
            etiquetas,
            "toxicologia de dosis repetidas",
            Severidad.ALTA,
        )
    )

    # Coherencia interna: el NOAEL tiene que quedar por debajo del LOAEL.
    if (
        estudio.noael is not None
        and estudio.loael is not None
        and estudio.noael.presente
        and estudio.loael.presente
    ):
        noael = estudio.noael.valor.exigir()
        loael = estudio.loael.valor.exigir()
        if noael >= loael:
            hallazgos.append(
                Hallazgo(
                    parametro="Coherencia NOAEL / LOAEL",
                    clase=ClaseHallazgo.DISCREPANCIA_ARITMETICA,
                    severidad=Severidad.ALTA,
                    observacion=(
                        f"El NOAEL declarado ({noael}) no es menor que el LOAEL "
                        f"declarado ({loael}). Por definicion la dosis sin efecto "
                        f"adverso observado debe quedar por debajo de la dosis mas "
                        f"baja con efecto adverso observado."
                    ),
                    etiquetas=etiquetas,
                )
            )

    # Margen de seguridad recalculado a partir del NOAEL y la dosis clinica.
    if (
        estudio.noael is not None
        and estudio.noael.presente
        and estudio.dosis_clinica_equivalente is not None
        and estudio.dosis_clinica_equivalente.presente
    ):
        derivado = derivar(
            nombre="Margen de seguridad (NOAEL / dosis clinica propuesta)",
            formula="noael / dosis_clinica",
            componentes=(
                ("noael", estudio.noael.valor.exigir()),
                ("dosis_clinica", estudio.dosis_clinica_equivalente.valor.exigir()),
            ),
            operacion=lambda n, d: n / d,
            unidad="veces",
        )
        contraste = contrastar_derivado(
            derivado,
            estudio.margen_seguridad_declarado,
            severidad_si_discrepa=Severidad.ALTA,
            etiquetas=etiquetas,
        )
        if contraste is not None:
            hallazgos.append(contraste)
    elif estudio.margen_seguridad_declarado is not None and estudio.margen_seguridad_declarado.presente:
        hallazgos.append(
            Hallazgo(
                parametro="Margen de seguridad declarado",
                clase=ClaseHallazgo.NO_COMPARABLE,
                severidad=Severidad.MEDIA,
                observacion=(
                    f"El expediente declara un margen de seguridad de "
                    f"{estudio.margen_seguridad_declarado.exigir()} pero no aporta a la "
                    f"vez el NOAEL y la dosis clinica propuesta que lo producirian. "
                    f"El agente no puede reproducir el calculo."
                ),
                etiquetas=etiquetas,
            )
        )

    # Un hallazgo toxicologico sin reversibilidad declarada no es interpretable.
    if estudio.organo_blanco is not None and estudio.organo_blanco.presente:
        if estudio.reversibilidad is None or not estudio.reversibilidad.presente:
            hallazgos.append(
                Hallazgo(
                    parametro=f"Reversibilidad del hallazgo en {estudio.organo_blanco.exigir()}",
                    clase=ClaseHallazgo.RESULTADO_NO_SUMINISTRADO,
                    severidad=Severidad.ALTA,
                    observacion=(
                        f"El estudio identifica un organo blanco "
                        f"({estudio.organo_blanco.exigir()}) pero no declara si el "
                        f"hallazgo revierte al suspender la exposicion. Sin ese dato el "
                        f"hallazgo no es interpretable: no se distingue una alteracion "
                        f"transitoria de un dano establecido."
                    ),
                    etiquetas=etiquetas,
                )
            )

    return hallazgos


def _auditar_reproductiva(estudio: EstudioReproductivo | None) -> list[Hallazgo]:
    if estudio is None:
        return [
            Hallazgo(
                parametro="Toxicologia reproductiva",
                clase=ClaseHallazgo.RESULTADO_NO_SUMINISTRADO,
                severidad=Severidad.ALTA,
                observacion=(
                    "El expediente no aporta estudio de toxicologia reproductiva. "
                    "El agente no infiere ausencia de riesgo a partir de ausencia de "
                    "estudio."
                ),
                etiquetas=ETIQUETAS_REPRO,
            )
        ]

    hallazgos: list[Hallazgo] = []
    etiquetas = ETIQUETAS_REPRO + (f"estudio:{estudio.estudio_id.valor or 'sin id'}",)

    for nombre, dato in (
        ("Periodo de exposicion gestacional", estudio.periodo_exposicion),
        ("Categoria de riesgo en embarazo declarada", estudio.categoria_embarazo_declarada),
    ):
        faltante = campo_ausente(nombre, dato, etiquetas)
        if faltante is not None:
            hallazgos.append(faltante)

    if (
        estudio.transferencia_placentaria is not None
        and estudio.transferencia_placentaria.presente
    ):
        valor = estudio.transferencia_placentaria.valor.exigir()
        if valor > UMBRAL_TRANSFERENCIA_PLACENTARIA:
            hallazgos.append(
                Hallazgo(
                    parametro="Transferencia placentaria",
                    clase=ClaseHallazgo.TENDENCIA_ADVERSA,
                    severidad=Severidad.ALTA,
                    observacion=(
                        f"La transferencia placentaria declarada es {valor}% de la "
                        f"dosis materna, por encima del umbral de "
                        f"{UMBRAL_TRANSFERENCIA_PLACENTARIA}% con que el agente eleva "
                        f"este parametro para lectura humana. Ese umbral es criterio "
                        f"operativo del agente y no proviene del expediente: la "
                        f"molecula atraviesa la barrera placentaria y la exposicion "
                        f"fetal es directa."
                    ),
                    medicion=estudio.transferencia_placentaria,
                    etiquetas=etiquetas,
                )
            )

    # Malformaciones sin frecuencia por grupo de dosis no permiten leer la
    # relacion dosis-respuesta, que es justamente lo que decide la etiqueta.
    sin_frecuencia = [
        m.tipo.valor
        for m in estudio.malformaciones
        if m.frecuencia is None or not m.frecuencia.presente
    ]
    if sin_frecuencia:
        hallazgos.append(
            Hallazgo(
                parametro="Frecuencia de las malformaciones descritas",
                clase=ClaseHallazgo.NO_COMPARABLE,
                severidad=Severidad.ALTA,
                observacion=(
                    f"El expediente describe {len(sin_frecuencia)} tipo(s) de "
                    f"malformacion ({', '.join(str(t) for t in sin_frecuencia)}) sin "
                    f"declarar frecuencia por grupo de dosis. Sin frecuencia no se "
                    f"puede leer la relacion dosis-respuesta ni comparar contra el "
                    f"grupo control."
                ),
                etiquetas=etiquetas,
            )
        )

    # Riesgo reproductivo declarado sin medida de mitigacion en el expediente.
    hay_senal = (
        (estudio.abortos_espontaneos is not None and estudio.abortos_espontaneos.presente)
        or bool(estudio.malformaciones)
    )
    sin_mitigacion = (
        estudio.medida_mitigacion_declarada is None
        or not estudio.medida_mitigacion_declarada.presente
    )
    if hay_senal and sin_mitigacion:
        hallazgos.append(
            Hallazgo(
                parametro="Medida de mitigacion del riesgo reproductivo",
                clase=ClaseHallazgo.RESULTADO_NO_SUMINISTRADO,
                severidad=Severidad.CRITICA,
                observacion=(
                    "El estudio reproductivo reporta hallazgos fetales adversos y el "
                    "expediente no declara ninguna medida de mitigacion asociada "
                    "(programa de prevencion de embarazo, condiciones de prescripcion "
                    "u otra). El agente reporta la ausencia; definir la medida "
                    "corresponde al evaluador."
                ),
                etiquetas=etiquetas,
            )
        )

    return hallazgos


def auditar_evidencia_no_clinica(
    farmacocinetica: EstudioFarmacocinetico | None,
    toxicologia: tuple[EstudioToxicologia, ...],
    reproductiva: EstudioReproductivo | None,
    especificaciones: Mapping[str, Especificacion],
) -> ReporteNoClinico:
    hallazgos: list[Hallazgo] = []
    hallazgos.extend(_auditar_pk(farmacocinetica, especificaciones))
    if not toxicologia:
        hallazgos.append(
            Hallazgo(
                parametro="Toxicologia de dosis repetidas",
                clase=ClaseHallazgo.RESULTADO_NO_SUMINISTRADO,
                severidad=Severidad.ALTA,
                observacion=(
                    "El expediente no aporta estudios de toxicologia de dosis "
                    "repetidas. No hay NOAEL contra el cual situar la dosis clinica."
                ),
                etiquetas=ETIQUETAS_TOX,
            )
        )
    for estudio in toxicologia:
        hallazgos.extend(_auditar_toxicologia(estudio, especificaciones))
    hallazgos.extend(_auditar_reproductiva(reproductiva))
    return ReporteNoClinico(
        farmacocinetica=farmacocinetica,
        toxicologia=toxicologia,
        reproductiva=reproductiva,
        hallazgos=tuple(hallazgos),
    )
