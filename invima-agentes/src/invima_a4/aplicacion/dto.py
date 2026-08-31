"""Construccion del payload de salida del Agente 4.

Mismo contrato que el A3: cada valor con su origen y su traza, ningun estado
global del expediente, y un bloque `decision` que solo el evaluador diligencia.
La diferencia esta en el ultimo bloque -- donde el borrador ponia un balance
ponderado y una recomendacion, este payload pone la mesa ordenada y las
preguntas abiertas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence

from invima_a1.domain.modelos import ContenidoSospechoso

from ..domain.modelos import Hallazgo
from ..domain.modulo45 import ExpedienteEvidencia
from ..domain.servicios.balance import InsumosBalance
from ..domain.servicios.cruce_toxico_clinico import ReporteCruce
from ..domain.servicios.ensayo_pivotal import ReporteEnsayo
from ..domain.servicios.farmacovigilancia import ReportePBRER
from ..domain.servicios.inmunogenicidad import ReporteInmunogenicidad
from ..domain.servicios.motor import ResumenAuditoria, ordenar
from ..domain.servicios.preclinico import ReporteNoClinico

AVISO_ALCANCE = (
    "Documento de apoyo tecnico. Estructura la evidencia que el expediente aporta, "
    "verifica que sus propios numeros concuerden entre si y senala lo que falta. No "
    "pondera beneficio contra riesgo, no propone un sentido para el tramite y no "
    "sustituye el concepto de la Comision Revisora: la valoracion cientifica y la "
    "decision administrativa son del servidor publico competente "
    "(art. 7.1, Resolucion 2026025611)."
)


def construir_payload(
    expediente: ExpedienteEvidencia,
    no_clinico: ReporteNoClinico,
    ensayo: ReporteEnsayo,
    inmunogenicidad: ReporteInmunogenicidad,
    pbrer: ReportePBRER,
    cruce: ReporteCruce,
    insumos: InsumosBalance,
    resumen: ResumenAuditoria,
    hallazgos: Sequence[Hallazgo],
    contenido_sospechoso: Sequence[ContenidoSospechoso],
    procedencia_expediente: str,
    momento: datetime,
) -> dict[str, Any]:
    return {
        "agente": "A4 - Auditoria de evidencia cientifica y clinica (Modulos 4, 5 y 7)",
        "aviso_de_alcance": AVISO_ALCANCE,
        "radicado": expediente.radicado,
        "producto": expediente.producto.a_dict(),
        "generado": momento.isoformat(),
        "procedencia_del_expediente": procedencia_expediente,
        "resumen": resumen.a_dict(),
        "hallazgos": [h.a_dict() for h in ordenar(hallazgos)],
        "evidencia_no_clinica": no_clinico.a_dict(),
        "evidencia_clinica": ensayo.a_dict(),
        "inmunogenicidad": inmunogenicidad.a_dict(),
        "farmacovigilancia": pbrer.a_dict(),
        "cruce_toxico_clinico": cruce.a_dict(),
        "plan_gestion_riesgos": (
            expediente.plan_riesgos.a_dict() if expediente.plan_riesgos else None
        ),
        "insumos_para_el_balance": insumos.a_dict(),
        "contenido_sospechoso": [
            {
                "campo": c.campo,
                "fragmento": c.fragmento,
                "motivo": c.motivo,
                "trazabilidad": c.traza.a_dict() if c.traza else None,
            }
            for c in contenido_sospechoso
        ],
        "decision": {
            "estado": "PENDIENTE_DE_LECTURA_HUMANA",
            "responsable": None,
            "nota": (
                "El agente no emite estado del expediente ni balance. Este campo lo "
                "diligencia el evaluador al registrar su lectura."
            ),
        },
    }
