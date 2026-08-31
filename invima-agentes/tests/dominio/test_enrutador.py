from __future__ import annotations

import pytest

from invima_a1.domain.servicios.enrutador import (
    GRUPO_FARMACOLOGIA,
    SECRETARIA_SEMPB,
    Prioridad,
    Ruta,
    recomendar_ruta,
)
from invima_a1.domain.servicios.motor_normativo import EstatusMolecula
from invima_a1.domain.valores import OrigenDato


def test_molecula_nueva_va_por_ruta_express():
    r = recomendar_ruta(EstatusMolecula.NUEVA, pago_conforme=True)
    assert r.ruta.valor == str(Ruta.EXPRESS)
    assert r.destino_primario.valor == SECRETARIA_SEMPB
    assert r.prioridad.valor == str(Prioridad.ALTA)
    assert len(r.destinos_paralelos) == 2


def test_molecula_conocida_va_por_ruta_estandar():
    r = recomendar_ruta(EstatusMolecula.CONOCIDA, pago_conforme=True)
    assert r.ruta.valor == str(Ruta.ESTANDAR)
    assert r.destino_primario.valor == GRUPO_FARMACOLOGIA
    assert len(r.destinos_paralelos) == 3


def test_pago_inconsistente_suspende_sin_importar_el_estatus():
    for estatus in (EstatusMolecula.NUEVA, EstatusMolecula.CONOCIDA):
        r = recomendar_ruta(estatus, pago_conforme=False, motivo_suspension="Valor no cuadra")
        assert r.ruta.valor == str(Ruta.SUSPENDIDA)
        assert r.destinos_paralelos == ()
        assert "Valor no cuadra" in r.razon


def test_estatus_indeterminado_no_bloquea_pero_avisa():
    r = recomendar_ruta(EstatusMolecula.INDETERMINADA, pago_conforme=True)
    assert r.ruta.valor == str(Ruta.ESTANDAR)
    assert "clasificacion manual" in r.razon


@pytest.mark.parametrize(
    "estatus", [EstatusMolecula.NUEVA, EstatusMolecula.CONOCIDA, EstatusMolecula.INDETERMINADA]
)
def test_toda_salida_del_enrutador_se_marca_como_recomendacion(estatus):
    """El enrutamiento nunca es una decision: el evaluador es quien reparte."""
    r = recomendar_ruta(estatus, pago_conforme=True)
    for dato in (r.ruta, r.destino_primario, r.prioridad):
        assert dato.origen is OrigenDato.RECOMENDACION


def test_la_razon_es_reproducible():
    """Dos corridas iguales producen la misma justificacion, palabra por palabra."""
    a = recomendar_ruta(EstatusMolecula.NUEVA, pago_conforme=True)
    b = recomendar_ruta(EstatusMolecula.NUEVA, pago_conforme=True)
    assert a.razon == b.razon
