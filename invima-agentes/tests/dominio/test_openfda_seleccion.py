"""Regresion de dos defectos que solo aparecieron al llamar a openFDA de verdad.

Los tests offline no podian verlos porque el adaptador nunca se habia ejecutado.

1. Con `limit=1`, buscar "metformin" devolvia como primer registro la etiqueta de
   SITAGLIPTINA + METFORMINA. Contrastar el dossier contra un producto combinado
   es un error de fondo: la indicacion aprobada del combinado no es la del
   principio activo aislado.
2. Varias moleculas tienen registros sin `indications_and_usage` mezclados con
   registros completos. Para bosentan, el primero venia vacio.

Se construyen respuestas de openFDA a mano: no hay red en estos tests.
"""

from __future__ import annotations

from invima_a1.adaptadores.salida.agencia_openfda import AgenciaOpenFDA
from invima_a1.domain.servicios.normalizacion import coinciden_dci, variantes_inn


def _registro(genericos: list[str], indicacion: str | None) -> dict:
    registro: dict = {"openfda": {"generic_name": genericos, "brand_name": ["MARCA"]}}
    if indicacion is not None:
        registro["indications_and_usage"] = [indicacion]
    return registro


COMBINADO = _registro(["SITAGLIPTIN AND METFORMIN HYDROCHLORIDE"], "Indicacion del combinado")
MONO_VACIO = _registro(["METFORMIN HYDROCHLORIDE"], None)
MONO_COMPLETO = _registro(["METFORMIN HYDROCHLORIDE"], "Type 2 diabetes mellitus in adults")


def test_no_escoge_el_producto_combinado_habiendo_monoingrediente():
    elegido, nota = AgenciaOpenFDA()._elegir([COMBINADO, MONO_COMPLETO], "Metformina")
    assert elegido is MONO_COMPLETO
    assert nota == ""


def test_salta_el_registro_sin_indicacion_si_hay_uno_completo():
    elegido, _ = AgenciaOpenFDA()._elegir([MONO_VACIO, MONO_COMPLETO], "Metformina")
    assert elegido is MONO_COMPLETO


def test_si_solo_hay_combinado_lo_advierte_de_forma_explicita():
    elegido, nota = AgenciaOpenFDA()._elegir([COMBINADO], "Metformina")
    assert elegido is COMBINADO
    assert "ADVERTENCIA" in nota
    assert "NO corresponde al principio activo aislado" in nota


def test_registro_sin_indicacion_se_entrega_avisando():
    elegido, nota = AgenciaOpenFDA()._elegir([MONO_VACIO], "Metformina")
    assert elegido is MONO_VACIO
    assert "verificacion directa del evaluador" in nota


def test_no_devuelve_una_molecula_ajena():
    ajeno = _registro(["METOPROLOL TARTRATE"], "Hypertension")
    elegido, nota = AgenciaOpenFDA()._elegir([ajeno], "Metformina")
    assert elegido is None
    assert "ninguno cuyo principio activo corresponda" in nota


def test_la_dci_espanola_encuentra_el_inn_ingles():
    """Sin esto, ningun dossier colombiano encontraria su molecula en FDA."""
    assert variantes_inn("Clorhidrato de Metformina") == ("metformina", "metformin")
    assert coinciden_dci("Clorhidrato de Metformina", "METFORMIN HYDROCHLORIDE")
    assert coinciden_dci("Omeprazol", "OMEPRAZOLE")


def test_las_variantes_no_confunden_moleculas_distintas():
    assert not coinciden_dci("Metformina", "Metoprolol")
    assert not coinciden_dci("Amlodipino", "Amiodarona")


def test_molecula_sin_terminacion_traducible_queda_igual():
    assert variantes_inn("Bosentan") == ("bosentan",)
