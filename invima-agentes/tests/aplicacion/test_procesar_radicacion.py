"""Pruebas del caso de uso completo, sin red y sin consumir credito.

Todo corre con los adaptadores locales: el parser lee el sidecar Markdown, el
extractor es determinista y las agencias devuelven "no consultado".
"""

from __future__ import annotations

from pathlib import Path

import pytest

from invima_a1.adaptadores.salida.auditoria_jsonl import AuditLogMemoria
from invima_a1.adaptadores.salida.extractor_fake import ExtractorDeterminista
from invima_a1.adaptadores.salida.normas_csv import NormasFarmacologicasCSV
from invima_a1.adaptadores.salida.parser_fake import ParserSidecarMarkdown
from invima_a1.adaptadores.salida.repo_sqlite import RepositorioMemoria
from invima_a1.adaptadores.salida.tarifas_csv import TarifarioCSV, TransaccionesCSV
from invima_a1.aplicacion.procesar_radicacion import (
    Dependencias,
    ProcesarRadicacionUseCase,
)
from invima_a1.aplicacion.supervision import RegistrarDecisionHumana
from invima_a1.config import AgenciaSinRed, EnsayosSinRed
from invima_a1.domain.errores import TransicionIlegalError
from invima_a1.domain.estados import EstadoExpediente, SentidoDecision
from invima_a1.domain.valores import OrigenDato

RAIZ = Path(__file__).resolve().parents[2]
FIXTURES = RAIZ / "data" / "fixtures"
REFERENCIA = RAIZ / "data" / "referencia"


@pytest.fixture
def deps(reloj_fijo):
    return Dependencias(
        parser=ParserSidecarMarkdown(),
        extractor=ExtractorDeterminista(),
        tarifario=TarifarioCSV(REFERENCIA / "tarifas.csv"),
        transacciones=TransaccionesCSV(REFERENCIA / "transacciones.csv"),
        agencias=[
            AgenciaSinRed("FDA", "https://api.fda.gov/?q={consulta}"),
            AgenciaSinRed("EMA", "https://www.ema.europa.eu/?q={consulta}"),
        ],
        ensayos=EnsayosSinRed(),
        normas=NormasFarmacologicasCSV(REFERENCIA / "normas_farmacologicas.csv"),
        repositorio=RepositorioMemoria(),
        auditoria=AuditLogMemoria(),
        reloj=reloj_fijo,
    )


def _correr(deps, carpeta: str, radicado: str = "2026-REG-TEST"):
    return ProcesarRadicacionUseCase(deps).ejecutar(FIXTURES / carpeta, radicado)


def test_el_agente_siempre_termina_esperando_a_una_persona(deps):
    resultado = _correr(deps, "dossier_corazilimab")
    assert resultado.expediente.estado is EstadoExpediente.PENDIENTE_VALIDACION_HUMANA
    assert resultado.expediente.decision_humana is None
    assert (
        resultado.payload["supervision_humana"]["estado"]
        == "PENDIENTE DE VALIDACION MANUAL"
    )


def test_molecula_nueva_con_pago_conforme_recomienda_express(deps):
    payload = _correr(deps, "dossier_corazilimab").payload
    assert payload["radicacion"]["pago"]["verificado"]
    assert payload["evaluacion_normativa"]["estatus_molecula"]["valor"] == "NUEVA MOLECULA"
    assert payload["enrutamiento"]["ruta_recomendada"]["valor"] == "EXPRESS"


def test_pago_inconsistente_corta_el_flujo_antes_de_buscar(deps):
    """Control de costo y regla de negocio en el mismo punto."""
    resultado = _correr(deps, "dossier_pago_inconsistente")
    assert resultado.suspendido
    assert resultado.payload["evaluacion_normativa"] is None
    assert resultado.payload["validaciones_internacionales"][
        "reporte_coincidencia_internacional"
    ] is None
    acciones = {e.accion for e in resultado.expediente.eventos}
    assert not any("Consulta a" in a for a in acciones)


def test_molecula_conocida_recomienda_ruta_estandar(deps):
    payload = _correr(deps, "dossier_metformina").payload
    assert payload["evaluacion_normativa"]["estatus_molecula"]["valor"] == "MOLECULA CONOCIDA"
    assert payload["enrutamiento"]["ruta_recomendada"]["valor"] == "ESTANDAR"


def test_discrepancia_declarativa_se_eleva_al_evaluador(deps):
    payload = _correr(deps, "dossier_discrepancia_declarativa").payload
    discrepancia = payload["evaluacion_normativa"]["discrepancia_declarativa"]
    assert discrepancia is not None
    assert "verificacion del evaluador" in discrepancia["mensaje"]


def test_indicacion_mas_amplia_queda_marcada(deps):
    payload = _correr(deps, "dossier_indicacion_ampliada").payload
    contrastes = payload["validaciones_internacionales"][
        "reporte_coincidencia_internacional"
    ]["contrastes"]
    assert any(c["clase_contraste"] == "MAS_AMPLIA" for c in contrastes)


def test_la_inyeccion_de_prompt_no_altera_el_enrutamiento(deps):
    """El dossier pide EXPRESS a gritos; la ruta la decide el Manual, no el texto."""
    resultado = _correr(deps, "dossier_inyeccion_prompt")
    payload = resultado.payload

    hallazgos = payload["seguridad_y_trazabilidad"]["contenido_sospechoso_detectado"]
    assert hallazgos
    assert all(h["campo"].startswith("observaciones") for h in hallazgos)

    razon = payload["enrutamiento"]["razon"]
    assert "Manual de Normas Farmacologicas" in razon
    assert resultado.expediente.estado is EstadoExpediente.PENDIENTE_VALIDACION_HUMANA


def test_todo_campo_del_payload_declara_su_origen(deps):
    payload = _correr(deps, "dossier_corazilimab").payload
    validos = {str(o) for o in OrigenDato}
    for bloque in ("solicitante", "producto", "tramite"):
        for campo, dato in payload[bloque].items():
            assert dato["origen"] in validos, campo
            assert dato["trazabilidad"] is not None, campo


def test_campo_ausente_no_se_infiere(deps):
    payload = _correr(deps, "dossier_metformina").payload
    ncts = payload["seguridad_y_trazabilidad"]
    assert ncts is not None
    ruta = payload["tramite"]["ruta_estudio"]
    assert ruta["origen"] in {"EXTRAIDO", "NO_SUMINISTRADO"}


def test_el_log_reconstruye_la_corrida(deps):
    resultado = _correr(deps, "dossier_corazilimab")
    acciones = [e.accion for e in resultado.expediente.eventos]
    assert any("Ingesta" in a for a in acciones)
    assert any("Validacion transaccional" in a for a in acciones)
    assert any("Bypass check" in a for a in acciones)
    assert any("Recomendacion de enrutamiento" in a for a in acciones)
    assert deps.auditoria.eventos_de("2026-REG-TEST")


def test_solo_la_decision_humana_enruta(deps, reloj_fijo):
    resultado = _correr(deps, "dossier_corazilimab")
    assert resultado.expediente.estado is EstadoExpediente.PENDIENTE_VALIDACION_HUMANA

    accion = RegistrarDecisionHumana(
        repositorio=deps.repositorio, auditoria=deps.auditoria, reloj=reloj_fijo
    )
    payload = accion.ejecutar(
        radicado="2026-REG-TEST",
        usuario="evaluador.perez",
        sentido=SentidoDecision.APROBAR_ENRUTAMIENTO,
        observaciones="Verificado contra folios",
    )
    assert payload["radicacion"]["estado"] == "ENRUTADO"
    assert payload["supervision_humana"]["usuario_responsable"] == "evaluador.perez"
    assert all(payload["supervision_humana"]["checklist_evaluador"].values())


def test_decidir_sobre_un_expediente_inexistente_falla(deps, reloj_fijo):
    accion = RegistrarDecisionHumana(
        repositorio=deps.repositorio, auditoria=deps.auditoria, reloj=reloj_fijo
    )
    with pytest.raises(TransicionIlegalError):
        accion.ejecutar(
            radicado="NO-EXISTE",
            usuario="evaluador.perez",
            sentido=SentidoDecision.APROBAR_ENRUTAMIENTO,
        )


def test_dos_corridas_producen_el_mismo_resultado(deps):
    """Reproducibilidad: el evaluador debe poder repetir la corrida y ver lo mismo."""
    a = _correr(deps, "dossier_corazilimab", "R-1").payload
    b = _correr(deps, "dossier_corazilimab", "R-2").payload
    for bloque in ("solicitante", "producto", "enrutamiento", "evaluacion_normativa"):
        assert a[bloque] == b[bloque]
