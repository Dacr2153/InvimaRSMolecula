"""Bypass check: determina si la molecula esta incluida en normas farmacologicas.

Trata dos fuentes como independientes y las contrasta:

  1. El check declarativo que marco el solicitante en el formulario.
  2. El cruce determinista contra el Manual de Normas Farmacologicas.

Cuando discrepan, el sistema NO escoge una y descarta la otra en silencio. Levanta
una DiscrepanciaDeclarativa que se muestra al evaluador. Que el solicitante afirme
que su molecula es nueva cuando el Manual la registra es justamente el tipo de
senal que un evaluador necesita ver.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..valores import Dato, Traza
from .normalizacion import normalizar_dci


class EstatusMolecula(StrEnum):
    NUEVA = "NUEVA MOLECULA"
    CONOCIDA = "MOLECULA CONOCIDA"
    INDETERMINADA = "INDETERMINADA"


@dataclass(frozen=True, slots=True)
class RegistroNormaFarmacologica:
    """Entrada del Manual de Normas Farmacologicas."""

    dci: str
    norma: str
    forma_farmaceutica: str = ""
    indicacion: str = ""


@dataclass(frozen=True, slots=True)
class DiscrepanciaDeclarativa:
    """El solicitante declaro una cosa y el Manual dice otra."""

    declarado_por_solicitante: str
    hallado_en_manual: str
    mensaje: str


@dataclass(frozen=True, slots=True)
class ResultadoEvaluacionNormativa:
    estatus: Dato[str]
    check_declarativo_no_incluida: Dato[bool]
    verificacion_manual: Dato[str]
    coincidencias: tuple[RegistroNormaFarmacologica, ...] = ()
    discrepancia: DiscrepanciaDeclarativa | None = None

    @property
    def es_nueva_molecula(self) -> bool:
        return self.estatus.valor == EstatusMolecula.NUEVA


def evaluar_normas(
    principio_activo: Dato[str],
    check_no_incluida: Dato[bool],
    coincidencias_manual: tuple[RegistroNormaFarmacologica, ...],
    version_manual: str,
) -> ResultadoEvaluacionNormativa:
    """Cruza el check declarativo contra el Manual y determina el estatus.

    El Manual manda sobre la declaracion del solicitante, pero la discrepancia
    queda registrada y visible.
    """
    traza_manual = Traza(
        descripcion=f"Manual de Normas Farmacologicas de Colombia ({version_manual})"
    )

    if not principio_activo.presente:
        return ResultadoEvaluacionNormativa(
            estatus=Dato.ausente("Estatus normativo: falta el principio activo"),
            check_declarativo_no_incluida=check_no_incluida,
            verificacion_manual=Dato.ausente(
                "No se pudo consultar el Manual sin principio activo"
            ),
        )

    dci = principio_activo.exigir()
    hay_coincidencia = bool(coincidencias_manual)

    if hay_coincidencia:
        normas = ", ".join(r.norma for r in coincidencias_manual)
        verificacion = Dato.de_busqueda(
            f"Encontrada en el Manual de Normas Farmacologicas ({normas})",
            traza_manual,
        )
        estatus_valor = EstatusMolecula.CONOCIDA
    else:
        verificacion = Dato.de_busqueda(
            f"No encontrada en el Manual de Normas Farmacologicas "
            f"(normalizada como '{normalizar_dci(dci)}')",
            traza_manual,
        )
        estatus_valor = EstatusMolecula.NUEVA

    discrepancia: DiscrepanciaDeclarativa | None = None
    if check_no_incluida.presente:
        declaro_nueva = check_no_incluida.exigir()
        if declaro_nueva and hay_coincidencia:
            discrepancia = DiscrepanciaDeclarativa(
                declarado_por_solicitante="Molecula NO incluida en normas farmacologicas",
                hallado_en_manual=f"Registrada en {normas}",
                mensaje=(
                    "El solicitante declaro que la molecula no esta incluida en normas "
                    "farmacologicas, pero el cruce contra el Manual arroja coincidencia. "
                    "Requiere verificacion del evaluador."
                ),
            )
        elif not declaro_nueva and not hay_coincidencia:
            discrepancia = DiscrepanciaDeclarativa(
                declarado_por_solicitante="Molecula incluida en normas farmacologicas",
                hallado_en_manual="Sin coincidencia en el Manual",
                mensaje=(
                    "El solicitante declaro que la molecula esta incluida en normas "
                    "farmacologicas, pero no se encontro coincidencia en el Manual. "
                    "Requiere verificacion del evaluador."
                ),
            )

    return ResultadoEvaluacionNormativa(
        estatus=Dato.de_busqueda(str(estatus_valor), traza_manual),
        check_declarativo_no_incluida=check_no_incluida,
        verificacion_manual=verificacion,
        coincidencias=coincidencias_manual,
        discrepancia=discrepancia,
    )
