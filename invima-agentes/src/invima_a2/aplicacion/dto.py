"""Payload de salida del A2 y barrera contra salidas conclusivas."""

from __future__ import annotations

import re
from typing import Any

from invima_a1.domain.modelos import ContenidoSospechoso

from ..domain.errores import SalidaConclusivaError
from ..domain.servicios.clasificador_producto import Clasificacion
from ..domain.servicios.motor_alertas import Alerta, Severidad, severidad_maxima
from ..domain.servicios.validador_legal import VerificacionLegal
from ..domain.valores import Dato

#: Vocabulario que solo le corresponde al evaluador. Si aparece en un valor del
#: payload, la corrida falla en vez de entregar una calificacion.
#: Se revisan los VALORES, no las razones ni los mensajes: una alerta puede y
#: debe decir "no acredita apostilla" sin que eso sea una decision.
_VOCABULARIO_DECISORIO = re.compile(
    r"\b(aprobad[oa]|rechazad[oa]|niega|negad[oa]|cumple|no cumple|"
    r"conforme a derecho|procedente|improcedente|valid[oa] juridicamente)\b",
    re.IGNORECASE,
)


def _serializar(campos: dict[str, Any]) -> dict[str, Any]:
    return {
        clave: valor.a_dict() if isinstance(valor, Dato) else valor
        for clave, valor in campos.items()
    }


def _verificar_no_conclusivo(nodo: Any, ruta: str = "") -> None:
    """Recorre el payload buscando vocabulario decisorio en los valores."""
    if isinstance(nodo, dict):
        for clave, valor in nodo.items():
            if clave in ("mensaje", "esperado", "encontrado", "trazabilidad", "razon"):
                continue
            _verificar_no_conclusivo(valor, f"{ruta}.{clave}" if ruta else str(clave))
    elif isinstance(nodo, list):
        for indice, valor in enumerate(nodo):
            _verificar_no_conclusivo(valor, f"{ruta}[{indice}]")
    elif isinstance(nodo, str):
        if _VOCABULARIO_DECISORIO.search(nodo):
            raise SalidaConclusivaError(
                f"El campo '{ruta}' contiene vocabulario decisorio: '{nodo}'. "
                f"El A2 describe hallazgos; la calificacion es del evaluador."
            )


def construir_payload(
    *,
    radicado: str,
    estado: str,
    verificacion: VerificacionLegal,
    clasificacion: Clasificacion,
    alertas: tuple[Alerta, ...],
    estatus_normas_a1: dict[str, Any] | None,
    enrutamiento_a1: dict[str, Any] | None,
    sospechosos: tuple[ContenidoSospechoso, ...],
    modelo_usado: str,
) -> dict[str, Any]:
    """Arma el dictamen del A2 sin perder la procedencia de ningun campo."""
    maxima = severidad_maxima(alertas)

    payload: dict[str, Any] = {
        "dictamen": {
            "numero_radicado": radicado,
            "estado": estado,
            "agente": "A2-VICR",
            "severidad_maxima": str(maxima),
            "retiene_reparto": maxima is Severidad.CRITICA,
        },
        "validacion_legal_modulo1": {
            "poder_especial": _serializar(verificacion.poder),
            "certificado_existencia": _serializar(verificacion.certificado_existencia),
            "certificados_bpm": [_serializar(fila) for fila in verificacion.bpm],
            "coherencia_nit": _serializar(verificacion.coherencia_nit),
        },
        "clasificacion_taxonomica": {
            "dimension_producto": clasificacion.dimension.a_dict(),
            "ruta_estudio": clasificacion.ruta_estudio.a_dict(),
            "marco_normativo": clasificacion.marco_normativo.a_dict(),
            "senales_detectadas": list(clasificacion.senales_detectadas),
        },
        "heredado_del_a1": {
            "estatus_normas_farmacologicas": estatus_normas_a1,
            "enrutamiento_recomendado": enrutamiento_a1,
            "nota": (
                "El estatus frente al Manual de Normas Farmacologicas y la ruta "
                "EXPRESS/ESTANDAR los determino el A1. El A2 no los recalcula: los "
                "muestra junto a los hallazgos legales para que el coordinador "
                "decida con todo a la vista."
            ),
        },
        "alertas": [a.a_dict() for a in alertas],
        "seguridad_y_trazabilidad": {
            "modelo_utilizado": modelo_usado,
            "contenido_sospechoso_detectado": [
                {"campo": s.campo, "fragmento": s.fragmento, "motivo": s.motivo}
                for s in sospechosos
            ],
        },
        "supervision_humana": {
            "estado": "REQUIERE APROBACION DEL COORDINADOR DE GRUPOS",
            "checklist": {
                "validacion_legal_revisada": False,
                "clasificacion_confirmada": False,
                "reparto_autorizado": False,
            },
            "usuario_responsable": None,
            "firma_timestamp": None,
            "fundamento": (
                "El agente no reparte expedientes. Prepara el dictamen y lo entrega "
                "al Coordinador de Grupos, a quien corresponde la decision "
                "(art. 7.1, Resolucion 2026025611)."
            ),
        },
    }

    _verificar_no_conclusivo(
        {
            "validacion_legal_modulo1": payload["validacion_legal_modulo1"],
            "clasificacion_taxonomica": payload["clasificacion_taxonomica"],
        }
    )
    return payload
