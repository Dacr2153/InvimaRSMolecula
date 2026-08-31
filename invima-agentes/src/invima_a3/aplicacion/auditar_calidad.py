"""Caso de uso: auditar el Modulo 3 de un expediente.

Orquesta los servicios de dominio, arma el payload y lo somete a la guardia
lexica antes de devolverlo. Si el payload trae vocabulario decisorio, la corrida
falla: es preferible una excepcion en el tablero que un concepto no firmado.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping

from invima_a1.domain.auditoria import EventoAuditoria, TipoEvento
from invima_a1.domain.modelos import ContenidoSospechoso
from invima_a1.domain.servicios import sanitizador

from ..domain.errores import SalidaConclusivaError
from ..domain.modelos import Especificacion, Hallazgo, Severidad
from ..domain.modulo3 import ExpedienteCalidad
from ..domain.servicios.consistencia_lotes import evaluar_consistencia
from ..domain.servicios.envase_cierre import auditar_envase_cierre
from ..domain.servicios.estabilidad import ReporteEstudio, evaluar_estudio
from ..domain.servicios.inactivacion_viral import auditar_inactivacion_viral
from ..domain.servicios.motor_hallazgos import auditar_lexico, consolidar, ordenar
from ..domain.servicios.sustancia_activa import auditar_sustancia_activa
from ..puertos import AuditLogPort
from ..puertos.especificaciones import EspecificacionesPort
from ..puertos.expediente_calidad import ExpedienteCalidadPort
from .dto import construir_payload


@dataclass(frozen=True, slots=True)
class ResultadoAuditoria:
    payload: dict[str, Any]
    hallazgos: tuple[Hallazgo, ...]


def _resolver_especificaciones(
    declaradas: Mapping[str, Especificacion],
    fuente: EspecificacionesPort | None,
    parametros: tuple[str, ...],
) -> dict[str, Especificacion]:
    """Completa con fuente normativa solo los parametros que el dossier no declara.

    Precedencia deliberada: manda lo que declara el solicitante, porque es contra
    su propia declaracion que se le audita. La farmacopea entra donde el dossier
    calla, y entra citada.
    """
    resueltas = dict(declaradas)
    if fuente is None:
        return resueltas
    for parametro in parametros:
        if parametro in resueltas:
            continue
        encontrada = fuente.buscar(parametro)
        if encontrada is not None:
            resueltas[parametro] = encontrada
    return resueltas


def _parametros_mencionados(expediente: ExpedienteCalidad) -> tuple[str, ...]:
    nombres: list[str] = []

    def agregar(nombre: str) -> None:
        if nombre not in nombres:
            nombres.append(nombre)

    sustancia = expediente.sustancia_activa
    for medicion in (
        sustancia.viabilidad_banco_maestro,
        sustancia.viabilidad_banco_trabajo,
        sustancia.peso_molecular,
    ):
        if medicion is not None:
            agregar(medicion.parametro)
    for medicion in sustancia.perfil_glicosilacion:
        agregar(medicion.parametro)
    for medicion in expediente.proceso_viral.parametros_proceso:
        agregar(medicion.parametro)
    for etapa in expediente.proceso_viral.etapas:
        agregar(etapa.lrv.parametro)
    for lote in expediente.lotes:
        for medicion in lote.mediciones:
            agregar(medicion.parametro)
    for medicion in expediente.envase_cierre.ensayos:
        agregar(medicion.parametro)
    return tuple(nombres)


def auditar_calidad(
    radicado: str,
    lector: ExpedienteCalidadPort,
    auditoria: AuditLogPort,
    especificaciones_normativas: EspecificacionesPort | None = None,
    momento: datetime | None = None,
) -> ResultadoAuditoria:
    """Ejecuta la auditoria completa del Modulo 3 y devuelve payload y hallazgos."""
    momento = momento or datetime.now(UTC)
    auditoria.registrar(
        EventoAuditoria(
            momento=momento,
            tipo=TipoEvento.PASO_INICIADO,
            radicado=radicado,
            accion="Auditoria de calidad del Modulo 3",
            resultado="INICIADO",
            detalles={"procedencia": lector.procedencia},
        )
    )

    expediente = lector.leer(radicado)

    sospechoso: tuple[ContenidoSospechoso, ...] = sanitizador.revisar_campos(
        {ubicacion: texto for ubicacion, texto in expediente.textos_libres}
    )
    for item in sospechoso:
        auditoria.registrar(
            EventoAuditoria(
                momento=momento,
                tipo=TipoEvento.ALERTA,
                radicado=radicado,
                accion="Contenido sospechoso en texto libre del Modulo 3",
                resultado=item.motivo,
                detalles={"campo": item.campo, "fragmento": item.fragmento},
            )
        )

    especificaciones = _resolver_especificaciones(
        expediente.especificaciones_declaradas,
        especificaciones_normativas,
        _parametros_mencionados(expediente),
    )

    sustancia = auditar_sustancia_activa(expediente.sustancia_activa, especificaciones)
    viral = auditar_inactivacion_viral(expediente.proceso_viral, especificaciones)
    consistencia = evaluar_consistencia(expediente.lotes, especificaciones)
    estudios: list[ReporteEstudio] = [
        evaluar_estudio(estudio) for estudio in expediente.estudios_estabilidad
    ]
    envase = auditar_envase_cierre(expediente.envase_cierre, especificaciones)

    hallazgos: list[Hallazgo] = []
    hallazgos.extend(sustancia.hallazgos)
    hallazgos.extend(viral.hallazgos)
    hallazgos.extend(consistencia.hallazgos)
    for reporte in estudios:
        hallazgos.extend(reporte.hallazgos)
    hallazgos.extend(envase.hallazgos)
    hallazgos_ordenados = ordenar(hallazgos)

    resumen = consolidar(hallazgos_ordenados)

    payload = construir_payload(
        expediente=expediente,
        sustancia=sustancia,
        viral=viral,
        consistencia=consistencia,
        estabilidad=estudios,
        envase=envase,
        resumen=resumen,
        hallazgos=hallazgos_ordenados,
        contenido_sospechoso=sospechoso,
        procedencia_expediente=lector.procedencia,
        momento=momento,
    )

    desvios = auditar_lexico(payload)
    if desvios:
        auditoria.registrar(
            EventoAuditoria(
                momento=momento,
                tipo=TipoEvento.ALERTA,
                radicado=radicado,
                accion="Guardia lexica del payload de salida",
                resultado="VOCABULARIO_DECISORIO_DETECTADO",
                detalles={"desvios": [{"ruta": r, "termino": t} for r, t in desvios]},
            )
        )
        detalle = "; ".join(f"{ruta}: '{termino}'" for ruta, termino in desvios[:5])
        raise SalidaConclusivaError(
            f"El payload de salida contiene vocabulario decisorio ({detalle}). "
            f"El agente describe evidencia; no se pronuncia sobre el tramite."
        )

    for hallazgo in hallazgos_ordenados:
        if hallazgo.severidad is not Severidad.CRITICA:
            continue
        auditoria.registrar(
            EventoAuditoria(
                momento=momento,
                tipo=TipoEvento.ALERTA,
                radicado=radicado,
                accion=f"Hallazgo critico: {hallazgo.parametro}",
                resultado=str(hallazgo.clase),
                detalles={"observacion": hallazgo.observacion},
            )
        )

    auditoria.registrar(
        EventoAuditoria(
            momento=momento,
            tipo=TipoEvento.PASO_COMPLETADO,
            radicado=radicado,
            accion="Auditoria de calidad del Modulo 3",
            resultado=f"{len(hallazgos_ordenados)} hallazgos",
            detalles=resumen.a_dict(),
        )
    )

    return ResultadoAuditoria(payload=payload, hallazgos=hallazgos_ordenados)
