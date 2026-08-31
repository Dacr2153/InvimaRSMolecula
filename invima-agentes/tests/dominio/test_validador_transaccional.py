from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from invima_a1.domain.modelos import Pago, Tarifa, TransaccionBancaria
from invima_a1.domain.servicios.validador_transaccional import (
    CampoInconsistente,
    validar_pago,
)
from invima_a1.domain.valores import Dato, Dinero, Traza

TRAZA = Traza(descripcion="Modulo 1 > Datos de pago")
TARIFA = Tarifa(
    codigo="1004",
    concepto="Evaluacion farmacologica de medicamento nuevo",
    valor_esperado=Dinero(Decimal("14850000.00")),
)


def _pago(comprobante="BAN-1", codigo="1004", valor="14850000.00") -> Pago:
    return Pago(
        comprobante_numero=Dato.extraido(comprobante, TRAZA),
        codigo_tarifa=Dato.extraido(codigo, TRAZA),
        valor_pagado=Dato.extraido(Dinero(Decimal(valor)), TRAZA),
    )


def _transaccion(comprobante="BAN-1", valor="14850000.00") -> TransaccionBancaria:
    return TransaccionBancaria(
        comprobante_numero=comprobante,
        valor_recibido=Dinero(Decimal(valor)),
        fecha=date(2026, 8, 20),
    )


def test_pago_conforme():
    resultado = validar_pago(_pago(), TARIFA, _transaccion())
    assert resultado.conforme
    assert resultado.inconsistencias == ()


def test_valor_distinto_a_la_tarifa():
    resultado = validar_pago(
        _pago(valor="12000000.00"), TARIFA, _transaccion(valor="12000000.00")
    )
    assert not resultado.conforme
    assert any(i.campo is CampoInconsistente.VALOR for i in resultado.inconsistencias)


def test_comprobante_inexistente_en_la_base():
    resultado = validar_pago(_pago(), TARIFA, None)
    assert not resultado.conforme
    campos = {i.campo for i in resultado.inconsistencias}
    assert CampoInconsistente.COMPROBANTE in campos


def test_codigo_de_tarifa_inexistente():
    resultado = validar_pago(_pago(codigo="9999"), None, _transaccion())
    assert not resultado.conforme
    assert any(
        i.campo is CampoInconsistente.CODIGO_TARIFA for i in resultado.inconsistencias
    )


def test_valor_declarado_distinto_al_recibido():
    resultado = validar_pago(_pago(), TARIFA, _transaccion(valor="14000000.00"))
    assert not resultado.conforme
    assert any("efectivamente recibido" in i.mensaje for i in resultado.inconsistencias)


@pytest.mark.parametrize(
    "campo", ["comprobante_numero", "codigo_tarifa", "valor_pagado"]
)
def test_campo_faltante_no_se_infiere(campo):
    base = _pago()
    pago = Pago(
        comprobante_numero=(
            Dato.ausente("Comprobante")
            if campo == "comprobante_numero"
            else base.comprobante_numero
        ),
        codigo_tarifa=(
            Dato.ausente("Codigo") if campo == "codigo_tarifa" else base.codigo_tarifa
        ),
        valor_pagado=(
            Dato.ausente("Valor") if campo == "valor_pagado" else base.valor_pagado
        ),
    )
    resultado = validar_pago(pago, TARIFA, _transaccion())
    assert not resultado.conforme
    assert any(
        i.campo is CampoInconsistente.DATO_FALTANTE for i in resultado.inconsistencias
    )
