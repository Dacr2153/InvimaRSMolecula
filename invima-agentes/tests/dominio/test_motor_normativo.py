from __future__ import annotations

from invima_a1.domain.servicios.motor_normativo import (
    EstatusMolecula,
    RegistroNormaFarmacologica,
    evaluar_normas,
)
from invima_a1.domain.servicios.normalizacion import coinciden_dci, normalizar_dci
from invima_a1.domain.valores import Dato, Traza

TRAZA = Traza(descripcion="Formulario > Seccion normativa")
METFORMINA = (
    RegistroNormaFarmacologica(
        dci="Metformina", norma="7.1.0.0.N10", indicacion="Diabetes tipo 2"
    ),
)


def test_sin_coincidencia_es_molecula_nueva():
    resultado = evaluar_normas(
        principio_activo=Dato.extraido("Corazilimab", TRAZA),
        check_no_incluida=Dato.extraido(True, TRAZA),
        coincidencias_manual=(),
        version_manual="v.2026",
    )
    assert resultado.es_nueva_molecula
    assert resultado.discrepancia is None


def test_con_coincidencia_es_molecula_conocida():
    resultado = evaluar_normas(
        principio_activo=Dato.extraido("Metformina", TRAZA),
        check_no_incluida=Dato.extraido(False, TRAZA),
        coincidencias_manual=METFORMINA,
        version_manual="v.2026",
    )
    assert resultado.estatus.valor == str(EstatusMolecula.CONOCIDA)
    assert resultado.discrepancia is None


def test_declara_nueva_pero_el_manual_la_registra():
    """El caso que un evaluador necesita ver: el Manual manda, y la discrepancia se eleva."""
    resultado = evaluar_normas(
        principio_activo=Dato.extraido("Metformina", TRAZA),
        check_no_incluida=Dato.extraido(True, TRAZA),
        coincidencias_manual=METFORMINA,
        version_manual="v.2026",
    )
    assert resultado.estatus.valor == str(EstatusMolecula.CONOCIDA)
    assert resultado.discrepancia is not None
    assert "7.1.0.0.N10" in resultado.discrepancia.hallado_en_manual


def test_declara_conocida_pero_no_esta_en_el_manual():
    resultado = evaluar_normas(
        principio_activo=Dato.extraido("Corazilimab", TRAZA),
        check_no_incluida=Dato.extraido(False, TRAZA),
        coincidencias_manual=(),
        version_manual="v.2026",
    )
    assert resultado.es_nueva_molecula
    assert resultado.discrepancia is not None


def test_sin_principio_activo_no_se_inventa_estatus():
    resultado = evaluar_normas(
        principio_activo=Dato.ausente("Principio activo"),
        check_no_incluida=Dato.extraido(True, TRAZA),
        coincidencias_manual=(),
        version_manual="v.2026",
    )
    assert resultado.estatus.valor is None
    assert not resultado.es_nueva_molecula


def test_normalizacion_de_sales_e_hidratos():
    assert normalizar_dci("Clorhidrato de Metformina") == "metformina"
    assert normalizar_dci("METFORMINA HCl") == "metformina"
    assert normalizar_dci("Losartan potasico") == "losartan"
    assert coinciden_dci("Amoxicilina trihidrato", "amoxicilina")
    assert not coinciden_dci("Metformina", "Metoprolol")
