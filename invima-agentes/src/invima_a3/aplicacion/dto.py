"""Construccion del payload de salida del Agente 3.

El JSON es el entregable: es lo que lee el evaluador en el tablero y lo que
queda archivado. Cada valor viaja con su origen y su traza, y el documento no
contiene ningun estado global del expediente -- solo hallazgos, conteos y las
preguntas abiertas que le quedan al especialista.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence

from invima_a1.domain.modelos import ContenidoSospechoso

from ..domain.modelos import Hallazgo
from ..domain.modulo3 import ExpedienteCalidad
from ..domain.servicios.consistencia_lotes import ReporteConsistencia
from ..domain.servicios.envase_cierre import ReporteEnvaseCierre
from ..domain.servicios.estabilidad import ReporteEstudio
from ..domain.servicios.inactivacion_viral import ReporteInactivacionViral
from ..domain.servicios.motor_hallazgos import ResumenAuditoria, ordenar
from ..domain.servicios.sustancia_activa import ReporteSustanciaActiva

AVISO_ALCANCE = (
    "Documento de apoyo tecnico. Describe la distancia entre lo que el expediente "
    "reporta y lo que el expediente declara como especificacion. No contiene ni "
    "sustituye el concepto de la Comision Revisora: la valoracion tecnica y la "
    "decision administrativa son del servidor publico competente "
    "(art. 7.1, Resolucion 2026025611)."
)


def construir_payload(
    expediente: ExpedienteCalidad,
    sustancia: ReporteSustanciaActiva,
    viral: ReporteInactivacionViral,
    consistencia: ReporteConsistencia,
    estabilidad: Sequence[ReporteEstudio],
    envase: ReporteEnvaseCierre,
    resumen: ResumenAuditoria,
    hallazgos: Sequence[Hallazgo],
    contenido_sospechoso: Sequence[ContenidoSospechoso],
    procedencia_expediente: str,
    momento: datetime,
) -> dict[str, Any]:
    return {
        "agente": "A3 - Auditoria de calidad y procesos (Modulo 3 / CMC)",
        "aviso_de_alcance": AVISO_ALCANCE,
        "radicado": expediente.radicado,
        "producto": expediente.producto.a_dict(),
        "generado": momento.isoformat(),
        "procedencia_del_expediente": procedencia_expediente,
        "resumen": resumen.a_dict(),
        "hallazgos": [h.a_dict() for h in ordenar(hallazgos)],
        "sustancia_activa": sustancia.a_dict(),
        "inactivacion_viral": viral.a_dict(),
        "consistencia_lotes": consistencia.a_dict(),
        "estabilidad": [r.a_dict() for r in estabilidad],
        "envase_cierre": envase.a_dict(),
        "especificaciones_declaradas": {
            nombre: espec.a_dict()
            for nombre, espec in expediente.especificaciones_declaradas.items()
        },
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
                "El agente no emite estado del expediente. Este campo lo diligencia "
                "el evaluador al registrar su lectura."
            ),
        },
    }
