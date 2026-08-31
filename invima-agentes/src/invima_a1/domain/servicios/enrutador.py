"""Enrutamiento del expediente.

Tabla de decision pura. La razon del enrutamiento no la redacta el modelo: se
compone a partir de la tabla, asi que es reproducible y auditable. Dos corridas
sobre el mismo expediente producen exactamente la misma justificacion.

El resultado es siempre una RECOMENDACION. Quien enruta es el evaluador.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..valores import Dato
from .motor_normativo import EstatusMolecula


class Ruta(StrEnum):
    EXPRESS = "EXPRESS"
    ESTANDAR = "ESTANDAR"
    SUSPENDIDA = "SUSPENDIDA"


class Prioridad(StrEnum):
    ALTA = "ALTA"
    NORMAL = "NORMAL"
    NINGUNA = "NINGUNA"


SECRETARIA_SEMPB = (
    "Secretaria de la Sala Especializada de Medicamentos y Productos Biologicos (SEMPB)"
)
GRUPO_FARMACOLOGIA = "Grupo de Evaluacion Farmacologica"
GRUPO_CALIDAD = "Grupo de Evaluacion de Calidad"
GRUPO_LEGAL = "Grupo de Evaluacion Legal"
GRUPO_FARMACOVIGILANCIA = "Grupo de Farmacovigilancia"


@dataclass(frozen=True, slots=True)
class Enrutamiento:
    ruta: Dato[str]
    destino_primario: Dato[str]
    destinos_paralelos: tuple[str, ...]
    prioridad: Dato[str]
    razon: str


def recomendar_ruta(
    estatus: EstatusMolecula | str,
    pago_conforme: bool,
    motivo_suspension: str = "",
) -> Enrutamiento:
    """Tabla de decision: (estatus de molecula, estado del pago) -> ruta recomendada."""
    if not pago_conforme:
        razon = (
            "Inconsistencia financiera detectada; el tramite no puede repartirse "
            "hasta que se subsane. " + motivo_suspension
        ).strip()
        return Enrutamiento(
            ruta=Dato.recomendado(str(Ruta.SUSPENDIDA), razon),
            destino_primario=Dato.recomendado(
                "Grupo de Radicacion (subsanacion)", razon
            ),
            destinos_paralelos=(),
            prioridad=Dato.recomendado(str(Prioridad.NINGUNA), razon),
            razon=razon,
        )

    if str(estatus) == str(EstatusMolecula.NUEVA):
        razon = (
            "Molecula NO incluida en el Manual de Normas Farmacologicas: no existe "
            "norma bajo la cual categorizarla, de modo que no procede el filtro de "
            "clasificacion previa. Pasa directamente a evaluacion farmacologica por "
            "la Sala Especializada (Decreto 1782 de 2014), con evaluacion tecnica en "
            "paralelo para no serializar los tiempos."
        )
        return Enrutamiento(
            ruta=Dato.recomendado(str(Ruta.EXPRESS), razon),
            destino_primario=Dato.recomendado(SECRETARIA_SEMPB, razon),
            destinos_paralelos=(GRUPO_FARMACOLOGIA, GRUPO_CALIDAD),
            prioridad=Dato.recomendado(str(Prioridad.ALTA), razon),
            razon=razon,
        )

    if str(estatus) == str(EstatusMolecula.CONOCIDA):
        razon = (
            "Molecula incluida en el Manual de Normas Farmacologicas. No requiere "
            "concepto previo de Sala; procede evaluacion concurrente por grupos."
        )
        return Enrutamiento(
            ruta=Dato.recomendado(str(Ruta.ESTANDAR), razon),
            destino_primario=Dato.recomendado(GRUPO_FARMACOLOGIA, razon),
            destinos_paralelos=(
                GRUPO_CALIDAD,
                GRUPO_LEGAL,
                GRUPO_FARMACOVIGILANCIA,
            ),
            prioridad=Dato.recomendado(str(Prioridad.NORMAL), razon),
            razon=razon,
        )

    razon = (
        "No fue posible determinar el estatus normativo de la molecula con la "
        "informacion del expediente. Se remite a evaluacion estandar para "
        "clasificacion manual por el evaluador."
    )
    return Enrutamiento(
        ruta=Dato.recomendado(str(Ruta.ESTANDAR), razon),
        destino_primario=Dato.recomendado(GRUPO_FARMACOLOGIA, razon),
        destinos_paralelos=(GRUPO_CALIDAD,),
        prioridad=Dato.recomendado(str(Prioridad.NORMAL), razon),
        razon=razon,
    )
