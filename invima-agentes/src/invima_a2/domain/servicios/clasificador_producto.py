"""Clasificacion taxonomica del producto.

Dos ejes que el A1 no mira porque no los necesita para enrutar, pero que
determinan que controles debe exigir el grupo evaluador:

  1. La dimension: sintesis quimica, biologico o vacuna. Cambia por completo la
     bateria de controles de calidad (pureza y ruta sintetica vs. linea celular e
     inmunogenicidad vs. inactivacion y cadena de frio).
  2. La ruta de estudio del Decreto 1782 de 2014 para biologicos: expediente
     completo, comparabilidad o comparabilidad abreviada.

El estatus frente al Manual de Normas Farmacologicas NO se resuelve aqui. Ese
cruce ya lo hace `motor_normativo` del A1 y el A2 lo consume del payload. Dos
implementaciones de la misma regla es exactamente lo que este agente evita.

Ante senal insuficiente devuelve INDETERMINADA. Adivinar la dimension de un
producto a partir de un formulario incompleto es peor que decir que no se sabe:
manda el expediente al grupo equivocado con apariencia de certeza.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from invima_a1.domain.servicios.normalizacion import sin_tildes

from ..modelos import PerfilProducto
from ..valores import Dato, Traza
from .motor_alertas import Alerta, Severidad, TipoAlerta


class DimensionProducto(StrEnum):
    SINTESIS_QUIMICA = "Sintesis quimica"
    BIOLOGICO = "Biologico / Biotecnologico"
    VACUNA = "Vacuna"
    INDETERMINADA = "INDETERMINADA"


class RutaEstudio(StrEnum):
    EXPEDIENTE_COMPLETO = "Expediente Completo"
    COMPARABILIDAD = "Comparabilidad"
    COMPARABILIDAD_ABREVIADA = "Comparabilidad Abreviada"
    NO_APLICA = "No aplica (producto no biologico)"
    INDETERMINADA = "INDETERMINADA"


#: Sistemas de expresion y terminos de banco celular. La presencia de cualquiera
#: es senal fuerte de biotecnologico: una molecula de sintesis no se produce en
#: celulas.
_SENALES_BIOLOGICO: tuple[str, ...] = (
    "cho", "hek", "sp2 0", "ns0", "e coli", "escherichia coli",
    "pichia", "saccharomyces", "levadura", "baculovirus", "celula de insecto",
    "linea celular", "banco celular", "master cell bank", "working cell bank",
    "mcb", "wcb", "proteina recombinante", "anticuerpo monoclonal",
    "hibridoma", "transfectada", "mamifera", "biotecnologico",
)

#: Vacunas. Se evaluan antes que biologicos: toda vacuna recombinante daria
#: positivo en las senales de arriba, y la clasificacion mas especifica manda.
_SENALES_VACUNA: tuple[str, ...] = (
    "vacuna", "antigeno", "semilla maestra", "cepa vacunal",
    "virus inactivado", "virus atenuado", "toxoide", "adyuvante",
    "plataforma antigenica", "inactivacion viral",
)

_SENALES_QUIMICA: tuple[str, ...] = (
    "sintesis quimica", "pequena molecula", "ruta sintetica",
    "cristalino", "polvo blanco", "impureza", "principio activo sintetico",
)


def _normalizar(texto: str | None) -> str:
    if not texto:
        return ""
    limpio = sin_tildes(texto).lower()
    return re.sub(r"[^a-z0-9\s]", " ", limpio)


def _coincidencias(texto: str, senales: tuple[str, ...]) -> list[str]:
    return [s for s in senales if s in texto]


@dataclass(frozen=True, slots=True)
class Clasificacion:
    dimension: Dato[str]
    ruta_estudio: Dato[str]
    marco_normativo: Dato[str]
    senales_detectadas: tuple[str, ...]
    alertas: tuple[Alerta, ...]


def clasificar_dimension(perfil: PerfilProducto) -> tuple[Dato[str], tuple[str, ...]]:
    """Determina la dimension a partir de las senales textuales del expediente."""
    fuentes = [
        perfil.forma_de_la_sustancia,
        perfil.sistema_de_expresion,
        perfil.banco_celular,
    ]
    texto = " ".join(_normalizar(d.valor if d else None) for d in fuentes)

    if not texto.strip():
        return (
            Dato.ausente(
                "Forma de la sustancia y sistema de expresion en el formulario"
            ),
            (),
        )

    vacuna = _coincidencias(texto, _SENALES_VACUNA)
    if vacuna:
        return (
            Dato.recomendado(
                str(DimensionProducto.VACUNA),
                "Senales de plataforma antigenica en el expediente: "
                + ", ".join(vacuna),
            ),
            tuple(vacuna),
        )

    biologico = _coincidencias(texto, _SENALES_BIOLOGICO)
    if biologico:
        return (
            Dato.recomendado(
                str(DimensionProducto.BIOLOGICO),
                "Senales de produccion en sistema vivo: " + ", ".join(biologico),
            ),
            tuple(biologico),
        )

    quimica = _coincidencias(texto, _SENALES_QUIMICA)
    if quimica:
        return (
            Dato.recomendado(
                str(DimensionProducto.SINTESIS_QUIMICA),
                "Senales de sintesis quimica: " + ", ".join(quimica),
            ),
            tuple(quimica),
        )

    return (
        Dato.recomendado(
            str(DimensionProducto.INDETERMINADA),
            "El expediente describe la sustancia pero sin terminos que permitan "
            "ubicarla en una dimension. Requiere clasificacion del evaluador",
        ),
        (),
    )


def determinar_ruta(
    perfil: PerfilProducto, dimension: str
) -> tuple[Dato[str], Dato[str]]:
    """Ruta de estudio del Decreto 1782 de 2014, solo para biologicos.

    Un producto de sintesis quimica no se evalua por esta via; devolver
    "Expediente Completo" para uno seria aplicarle un marco que no lo rige.
    """
    if dimension in (
        str(DimensionProducto.SINTESIS_QUIMICA),
        str(DimensionProducto.INDETERMINADA),
    ):
        marco = (
            Dato.recomendado(
                "Decreto 677 de 1995",
                "Medicamento de sintesis quimica: no le aplica el regimen de "
                "biologicos del Decreto 1782 de 2014",
            )
            if dimension == str(DimensionProducto.SINTESIS_QUIMICA)
            else Dato.ausente("Marco normativo, a la espera de clasificar la dimension")
        )
        ruta = (
            Dato.recomendado(
                str(RutaEstudio.NO_APLICA),
                "La ruta de estudio del Decreto 1782 de 2014 aplica a biologicos",
            )
            if dimension == str(DimensionProducto.SINTESIS_QUIMICA)
            else Dato.ausente("Ruta de estudio, a la espera de clasificar la dimension")
        )
        return ruta, marco

    marco = Dato.recomendado(
        "Decreto 1782 de 2014",
        f"Producto clasificado como {dimension}",
    )

    referencia = perfil.producto_referencia
    if referencia is not None and referencia.presente:
        return (
            Dato.recomendado(
                str(RutaEstudio.COMPARABILIDAD),
                "El expediente aporta estudios frente a un producto de referencia: "
                f"{referencia.exigir()}",
            ),
            marco,
        )

    modulos = {m.upper().replace(" ", "") for m in perfil.modulos_presentes}
    tiene_preclinico = any(m.startswith("M4") or m == "MODULO4" for m in modulos)
    tiene_clinico = any(m.startswith("M5") or m == "MODULO5" for m in modulos)

    if tiene_preclinico and tiene_clinico:
        return (
            Dato.recomendado(
                str(RutaEstudio.EXPEDIENTE_COMPLETO),
                "El expediente aporta Modulo 4 (preclinico) y Modulo 5 (clinico) "
                "sin producto de referencia declarado",
            ),
            marco,
        )

    if modulos:
        return (
            Dato.recomendado(
                str(RutaEstudio.COMPARABILIDAD_ABREVIADA),
                "Presentacion parcial: el expediente no aporta la totalidad de "
                f"Modulos 4 y 5 ni declara producto de referencia. Modulos: "
                f"{', '.join(sorted(modulos))}",
            ),
            marco,
        )

    return (
        Dato.ausente("Estructura de modulos del expediente"),
        marco,
    )


def clasificar(perfil: PerfilProducto) -> Clasificacion:
    """Clasificacion completa: dimension, ruta de estudio y marco aplicable."""
    dimension, senales = clasificar_dimension(perfil)
    valor_dimension = dimension.valor or str(DimensionProducto.INDETERMINADA)
    ruta, marco = determinar_ruta(perfil, valor_dimension)

    alertas: list[Alerta] = []
    if valor_dimension == str(DimensionProducto.INDETERMINADA):
        alertas.append(
            Alerta(
                tipo=TipoAlerta.CLASIFICACION_INDETERMINADA,
                severidad=Severidad.MEDIA,
                mensaje=(
                    "No fue posible ubicar el producto en una dimension a partir del "
                    "expediente. La bateria de controles de calidad depende de esto"
                ),
                esperado="Forma de la sustancia o sistema de expresion identificables",
                encontrado="Sin senales concluyentes",
                traza=Traza(
                    descripcion="Clasificacion taxonomica sobre el formulario ASS-RSA-FM113"
                ),
            )
        )

    return Clasificacion(
        dimension=dimension,
        ruta_estudio=ruta,
        marco_normativo=marco,
        senales_detectadas=senales,
        alertas=tuple(alertas),
    )
