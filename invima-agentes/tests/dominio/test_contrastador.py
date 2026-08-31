from __future__ import annotations

from datetime import date

from invima_a1.domain.modelos import AprobacionAgencia
from invima_a1.domain.servicios.contrastador_indicaciones import (
    ClaseContraste,
    clasificar_contraste,
    contrastar_indicaciones,
)
from invima_a1.domain.valores import Dato, Traza

FUENTE = Traza.en_fuente_publica("FDA", "https://api.fda.gov/drug/label.json")


def test_indicaciones_identicas_coinciden():
    assert (
        clasificar_contraste(
            "Hipertension arterial pulmonar en adultos",
            "Hipertension arterial pulmonar en adultos",
        )
        is ClaseContraste.COINCIDENTE
    )


def test_indicacion_solicitada_mas_amplia():
    clase = clasificar_contraste(
        "Nefropatia diabetica en adultos, adolescentes, poblacion pediatrica y "
        "pacientes geriatricos con insuficiencia hepatica",
        "Nefropatia diabetica en adultos",
    )
    assert clase is ClaseContraste.MAS_AMPLIA


def test_indicacion_solicitada_mas_restringida():
    clase = clasificar_contraste(
        "Artritis reumatoide",
        "Artritis reumatoide, psoriasis en placas y enfermedad de Crohn",
    )
    assert clase is ClaseContraste.MAS_RESTRINGIDA


def test_indicaciones_ajenas_no_se_fuerzan_a_coincidir():
    clase = clasificar_contraste("Migrana episodica", "Diabetes mellitus tipo 2")
    assert clase is ClaseContraste.SIN_CORRESPONDENCIA


def test_sin_datos_no_es_evaluable():
    assert clasificar_contraste("", "Algo") is ClaseContraste.NO_EVALUABLE


def test_separa_lo_verificado_de_lo_declarado():
    """Distincion clave para el evaluador: que se comprobo y que solo se afirmo."""
    aprobaciones = (
        AprobacionAgencia(
            agencia="FDA",
            fecha_aprobacion=Dato.de_busqueda(date(2025, 10, 12), FUENTE),
            indicacion_aprobada=Dato.de_busqueda("Hipertension arterial pulmonar", FUENTE),
            declarada_por_solicitante=True,
            verificada_en_fuente=True,
        ),
        AprobacionAgencia(
            agencia="MHRA",
            fecha_aprobacion=Dato.ausente("Fecha"),
            indicacion_aprobada=Dato.ausente("Indicacion"),
            declarada_por_solicitante=True,
            verificada_en_fuente=False,
        ),
    )
    reporte = contrastar_indicaciones(
        "Corazilimab", "Hipertension arterial pulmonar", aprobaciones
    )
    assert reporte.agencias_que_aprobaron == ("FDA",)
    assert reporte.aprobaciones_declaradas_no_verificadas == ("MHRA",)


def test_marca_cuando_lo_solicitado_excede_lo_aprobado():
    aprobaciones = (
        AprobacionAgencia(
            agencia="FDA",
            fecha_aprobacion=Dato.de_busqueda(date(2024, 7, 8), FUENTE),
            indicacion_aprobada=Dato.de_busqueda("Nefropatia diabetica en adultos", FUENTE),
            verificada_en_fuente=True,
        ),
    )
    reporte = contrastar_indicaciones(
        "Renovaxina",
        "Nefropatia diabetica en adultos, adolescentes, poblacion pediatrica y "
        "pacientes geriatricos con insuficiencia hepatica",
        aprobaciones,
    )
    assert reporte.hay_indicacion_mas_amplia


def test_nunca_emite_juicio_de_aprobacion():
    """Ninguna observacion del contraste puede leerse como un concepto tecnico."""
    aprobaciones = (
        AprobacionAgencia(
            agencia="FDA",
            fecha_aprobacion=Dato.de_busqueda(date(2025, 1, 1), FUENTE),
            indicacion_aprobada=Dato.de_busqueda("Migrana episodica en adultos", FUENTE),
            verificada_en_fuente=True,
        ),
    )
    reporte = contrastar_indicaciones("Rapidexina", "Migrana episodica en adultos", aprobaciones)
    prohibidas = ("se aprueba", "se niega", "cumple", "no cumple", "procede el registro")
    for contraste in reporte.contrastes:
        texto = contraste.observacion.lower()
        assert not any(p in texto for p in prohibidas)
