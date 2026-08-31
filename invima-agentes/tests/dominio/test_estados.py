"""La garantia central del sistema: sin humano no hay enrutamiento.

Si algun dia alguien "optimiza" la maquina de estados y estos tests pasan a verde
por accidente, la propuesta queda descalificada segun las reglas de la Hackaton.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from invima_a1.domain.errores import TransicionIlegalError
from invima_a1.domain.estados import (
    DecisionHumana,
    EstadoExpediente,
    SentidoDecision,
    validar_transicion,
)
from invima_a1.domain.modelos import Expediente

AHORA = datetime(2026, 8, 26, 14, 0, tzinfo=UTC)


def _expediente(estado: EstadoExpediente) -> Expediente:
    return Expediente(
        radicado="2026-REG-TEST", fecha_radicacion=date(2026, 8, 26), estado=estado
    )


def test_el_agente_no_puede_enrutar_por_si_solo():
    expediente = _expediente(EstadoExpediente.PENDIENTE_VALIDACION_HUMANA)
    with pytest.raises(TransicionIlegalError, match="servidor publico competente"):
        expediente.avanzar_a(EstadoExpediente.ENRUTADO, AHORA)
    assert expediente.estado is EstadoExpediente.PENDIENTE_VALIDACION_HUMANA


def test_no_hay_atajo_desde_ruta_recomendada_hasta_enrutado():
    expediente = _expediente(EstadoExpediente.RUTA_RECOMENDADA)
    with pytest.raises(TransicionIlegalError):
        expediente.avanzar_a(EstadoExpediente.ENRUTADO, AHORA)


def test_con_decision_humana_si_enruta():
    expediente = _expediente(EstadoExpediente.PENDIENTE_VALIDACION_HUMANA)
    decision = DecisionHumana(
        usuario="evaluador.perez",
        sentido=SentidoDecision.APROBAR_ENRUTAMIENTO,
        momento=AHORA,
    )
    expediente.registrar_decision_humana(decision, AHORA)

    assert expediente.estado is EstadoExpediente.ENRUTADO
    assert expediente.exigir_decision_humana().usuario == "evaluador.perez"


def test_devolver_lleva_a_devuelto_por_evaluador():
    expediente = _expediente(EstadoExpediente.PENDIENTE_VALIDACION_HUMANA)
    expediente.registrar_decision_humana(
        DecisionHumana(
            usuario="evaluador.perez",
            sentido=SentidoDecision.DEVOLVER,
            momento=AHORA,
            observaciones="Falta el folio de BPM",
        ),
        AHORA,
    )
    assert expediente.estado is EstadoExpediente.DEVUELTO_POR_EVALUADOR


def test_una_decision_sin_responsable_es_invalida():
    with pytest.raises(TransicionIlegalError, match="servidor publico responsable"):
        DecisionHumana(
            usuario="   ",
            sentido=SentidoDecision.APROBAR_ENRUTAMIENTO,
            momento=AHORA,
        )


def test_la_decision_humana_queda_en_el_log_con_nombre():
    expediente = _expediente(EstadoExpediente.PENDIENTE_VALIDACION_HUMANA)
    expediente.registrar_decision_humana(
        DecisionHumana(
            usuario="evaluador.perez",
            sentido=SentidoDecision.CORREGIR_Y_APROBAR,
            momento=AHORA,
            campos_corregidos=("producto.concentracion",),
        ),
        AHORA,
    )
    actores = {e.actor for e in expediente.eventos}
    assert actores == {"evaluador.perez"}
    assert any("producto.concentracion" in str(e.detalles) for e in expediente.eventos)


def test_transicion_inventada_se_rechaza():
    with pytest.raises(TransicionIlegalError, match="no contemplada"):
        validar_transicion(EstadoExpediente.RECIBIDO, EstadoExpediente.ENRUTADO)
