"""Construccion del payload JSON de salida del agente A1-RCE.

El payload es lo que ve el evaluador y lo que consume el Agente 2. Cada campo
lleva su origen y su trazabilidad, y la seccion `supervision_humana` deja
constancia de que el tramite esta detenido esperando a una persona.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..domain.modelos import ContenidoSospechoso, Expediente
from ..domain.servicios.contrastador_indicaciones import (
    ReporteCoincidenciaInternacional,
)
from ..domain.servicios.enrutador import Enrutamiento
from ..domain.servicios.motor_normativo import ResultadoEvaluacionNormativa
from ..domain.servicios.validador_transaccional import ResultadoValidacionPago
from ..domain.valores import Dato


@dataclass(frozen=True, slots=True)
class DatosRadicacion:
    solicitante: dict[str, Dato[Any]]
    producto: dict[str, Dato[Any]]
    tramite: dict[str, Dato[Any]]
    pago: dict[str, Dato[Any]]
    certificado: dict[str, Dato[Any]]


def _serializar(campos: dict[str, Dato[Any]]) -> dict[str, Any]:
    return {nombre: dato.a_dict() for nombre, dato in campos.items()}


def construir_payload(
    expediente: Expediente,
    datos: DatosRadicacion,
    validacion_pago: ResultadoValidacionPago,
    reporte_internacional: ReporteCoincidenciaInternacional | None,
    evaluacion_normativa: ResultadoEvaluacionNormativa | None,
    enrutamiento: Enrutamiento | None,
    contenido_sospechoso: tuple[ContenidoSospechoso, ...],
    modelo_usado: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "radicacion": {
            "numero_radicado": expediente.radicado,
            "fecha_radicacion": expediente.fecha_radicacion.isoformat(),
            "estado": str(expediente.estado),
            "pago": _serializar(datos.pago)
            | {
                "verificado": validacion_pago.conforme,
                "resultado_validacion": validacion_pago.resumen,
                "inconsistencias": [
                    {
                        "campo": str(i.campo),
                        "esperado": i.esperado,
                        "encontrado": i.encontrado,
                        "mensaje": i.mensaje,
                    }
                    for i in validacion_pago.inconsistencias
                ],
            },
        },
        "solicitante": _serializar(datos.solicitante),
        "producto": _serializar(datos.producto),
        "tramite": _serializar(datos.tramite),
    }

    payload["validaciones_internacionales"] = {
        "certificado": _serializar(datos.certificado),
        "reporte_coincidencia_internacional": (
            {
                "molecula_identificada": reporte_internacional.molecula,
                "agencias_verificadas_en_fuente": list(
                    reporte_internacional.agencias_que_aprobaron
                ),
                "aprobaciones_declaradas_no_verificadas": list(
                    reporte_internacional.aprobaciones_declaradas_no_verificadas
                ),
                "contrastes": [
                    {
                        "agencia": c.agencia,
                        "indicacion_solicitada": c.indicacion_solicitada,
                        "indicacion_aprobada": c.indicacion_aprobada,
                        "clase_contraste": str(c.clase),
                        "observacion": c.observacion,
                        "fuente": c.fuente,
                    }
                    for c in reporte_internacional.contrastes
                ],
            }
            if reporte_internacional
            else None
        ),
    }

    payload["evaluacion_normativa"] = (
        {
            "estatus_molecula": evaluacion_normativa.estatus.a_dict(),
            "check_declarativo_no_incluida": (
                evaluacion_normativa.check_declarativo_no_incluida.a_dict()
            ),
            "verificacion_manual_normas": (
                evaluacion_normativa.verificacion_manual.a_dict()
            ),
            "coincidencias_manual": [
                {"dci": r.dci, "norma": r.norma, "indicacion": r.indicacion}
                for r in evaluacion_normativa.coincidencias
            ],
            "discrepancia_declarativa": (
                {
                    "declarado_por_solicitante": (
                        evaluacion_normativa.discrepancia.declarado_por_solicitante
                    ),
                    "hallado_en_manual": (
                        evaluacion_normativa.discrepancia.hallado_en_manual
                    ),
                    "mensaje": evaluacion_normativa.discrepancia.mensaje,
                }
                if evaluacion_normativa.discrepancia
                else None
            ),
        }
        if evaluacion_normativa
        else None
    )

    payload["enrutamiento"] = (
        {
            "ruta_recomendada": enrutamiento.ruta.a_dict(),
            "destino_primario": enrutamiento.destino_primario.a_dict(),
            "destinos_paralelos": list(enrutamiento.destinos_paralelos),
            "prioridad": enrutamiento.prioridad.a_dict(),
            "razon": enrutamiento.razon,
        }
        if enrutamiento
        else None
    )

    decision = expediente.decision_humana
    payload["supervision_humana"] = {
        "estado": (
            "PENDIENTE DE VALIDACION MANUAL"
            if decision is None
            else f"DECIDIDO POR EL EVALUADOR ({decision.sentido})"
        ),
        "advertencia": (
            "Este documento es un insumo de apoyo. No constituye concepto tecnico ni "
            "decision administrativa. La motivacion y la firma del acto corresponden "
            "al servidor publico competente (art. 7.1, Resolucion 2026025611)."
        ),
        "checklist_evaluador": {
            "datos_extraidos_validados": decision is not None,
            "busqueda_internacional_confirmada": decision is not None,
            "enrutamiento_aprobado": decision is not None,
        },
        "usuario_responsable": decision.usuario if decision else None,
        "sentido_decision": str(decision.sentido) if decision else None,
        "firma_timestamp": decision.momento.isoformat() if decision else None,
        "campos_corregidos": list(decision.campos_corregidos) if decision else [],
    }

    payload["seguridad_y_trazabilidad"] = {
        "separacion_epistemologica": {
            "EXTRAIDO": "Transcrito literalmente de un documento del expediente",
            "BUSQUEDA": "Recuperado de una fuente publica externa y citado con su URL",
            "RECOMENDACION": "Producido por logica determinista del agente; sugerencia, no decision",
            "NO_SUMINISTRADO": "Campo buscado y ausente en el expediente; no se infiere",
        },
        "modelo_utilizado": modelo_usado,
        "defensa_prompt_injection": (
            "El contenido del dossier se procesa como dato delimitado, nunca como "
            "instruccion. La salida del modelo se valida contra esquema cerrado."
        ),
        "contenido_sospechoso_detectado": [
            {
                "campo": c.campo,
                "fragmento": c.fragmento,
                "motivo": c.motivo,
            }
            for c in contenido_sospechoso
        ],
        "auditoria_log": [e.a_dict() for e in expediente.eventos],
    }

    return payload
