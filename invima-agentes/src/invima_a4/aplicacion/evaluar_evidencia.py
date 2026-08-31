"""Caso de uso: auditar la evidencia cientifica de un expediente.

Orquesta los servicios, arma los insumos del balance y somete el payload a la
guardia lexica antes de devolverlo. Si el documento trae vocabulario decisorio,
la corrida falla: en este agente esa barrera es la que separa un informe de
apoyo de un concepto sin firma.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from invima_a1.domain.auditoria import EventoAuditoria, TipoEvento
from invima_a1.domain.modelos import ContenidoSospechoso
from invima_a1.domain.servicios import sanitizador

from ..domain.errores import SalidaConclusivaError
from ..domain.modelos import Hallazgo, Severidad
from ..domain.modulo45 import ExpedienteEvidencia
from ..domain.servicios.balance import (
    BeneficioDeclarado,
    RiesgoDeclarado,
    armar_insumos,
)
from ..domain.servicios.cruce_toxico_clinico import cruzar, sistemas_de
from ..domain.servicios.ensayo_pivotal import TipoDesenlace, auditar_ensayo_pivotal
from ..domain.servicios.farmacovigilancia import auditar_pbrer
from ..domain.servicios.inmunogenicidad import auditar_inmunogenicidad
from ..domain.servicios.motor import auditar_lexico, consolidar, ordenar
from ..domain.servicios.preclinico import auditar_evidencia_no_clinica
from ..puertos import AuditLogPort
from ..puertos.expediente_evidencia import ExpedienteEvidenciaPort
from .dto import construir_payload


@dataclass(frozen=True, slots=True)
class ResultadoEvaluacion:
    payload: dict[str, Any]
    hallazgos: tuple[Hallazgo, ...]


def _beneficios(expediente: ExpedienteEvidencia) -> list[BeneficioDeclarado]:
    """Los desenlaces que el expediente declara, con su contraste y su folio.

    Ningun desenlace se pondera ni se califica de relevante: se transcribe con
    lo que hace falta para que el evaluador lo lea.
    """
    ensayo = expediente.ensayo_pivotal
    if ensayo is None:
        return []
    alfa = (
        ensayo.alfa_prespecificado.exigir()
        if ensayo.alfa_prespecificado is not None and ensayo.alfa_prespecificado.presente
        else None
    )
    beneficios: list[BeneficioDeclarado] = []
    for desenlace in ensayo.desenlaces:
        if desenlace.tipo is TipoDesenlace.SEGURIDAD:
            continue
        p = (
            desenlace.p_valor.exigir()
            if desenlace.p_valor is not None and desenlace.p_valor.presente
            else None
        )
        traza = None
        if desenlace.valor_intervencion is not None and desenlace.valor_intervencion.valor.traza:
            traza = desenlace.valor_intervencion.valor.traza.a_dict()
        beneficios.append(
            BeneficioDeclarado(
                desenlace=desenlace.metrica,
                tipo=str(desenlace.tipo),
                valor_intervencion=(
                    desenlace.valor_intervencion.a_dict()
                    if desenlace.valor_intervencion
                    else None
                ),
                valor_control=(
                    desenlace.valor_control.a_dict() if desenlace.valor_control else None
                ),
                p_valor=float(p) if p is not None else None,
                umbral_prespecificado=float(alfa) if alfa is not None else None,
                queda_bajo_el_umbral=(
                    None if (p is None or alfa is None) else bool(p < alfa)
                ),
                trazabilidad=traza,
            )
        )
    return beneficios


def _riesgos(expediente: ExpedienteEvidencia) -> list[RiesgoDeclarado]:
    """Los riesgos que el expediente declara, con la mitigacion que el propio
    solicitante propone. Si no propone ninguna, el campo queda vacio -- el
    agente no inventa la medida."""
    riesgos: list[RiesgoDeclarado] = []
    plan = expediente.plan_riesgos

    def mitigacion_para(texto: str) -> str | None:
        if plan is None:
            return None
        sistemas = sistemas_de(texto)
        for riesgo in plan.riesgos_listados:
            if not riesgo.presente:
                continue
            if sistemas & sistemas_de(str(riesgo.exigir())):
                return str(riesgo.exigir())
        return None

    reproductiva = expediente.reproductiva
    if reproductiva is not None and reproductiva.malformaciones:
        tipos = ", ".join(
            str(m.tipo.valor) for m in reproductiva.malformaciones if m.tipo.presente
        )
        descripcion = f"Hallazgos fetales adversos en el estudio reproductivo: {tipos}"
        declarada = (
            str(reproductiva.medida_mitigacion_declarada.exigir())
            if reproductiva.medida_mitigacion_declarada is not None
            and reproductiva.medida_mitigacion_declarada.presente
            else mitigacion_para(descripcion)
        )
        riesgos.append(
            RiesgoDeclarado(
                descripcion=descripcion,
                origen="Evidencia no clinica (Modulo 4.4)",
                frecuencia=(
                    "No declarada por grupo de dosis"
                    if any(
                        m.frecuencia is None or not m.frecuencia.presente
                        for m in reproductiva.malformaciones
                    )
                    else None
                ),
                mitigacion_declarada=declarada,
                trazabilidad=(
                    reproductiva.estudio_id.traza.a_dict()
                    if reproductiva.estudio_id.traza
                    else None
                ),
            )
        )

    for estudio in expediente.toxicologia:
        if estudio.organo_blanco is None or not estudio.organo_blanco.presente:
            continue
        descripcion = (
            f"Organo blanco identificado en toxicologia de dosis repetidas: "
            f"{estudio.organo_blanco.exigir()}"
        )
        riesgos.append(
            RiesgoDeclarado(
                descripcion=descripcion,
                origen="Evidencia no clinica (Modulo 4.3)",
                frecuencia=None,
                mitigacion_declarada=mitigacion_para(descripcion),
                trazabilidad=(
                    estudio.organo_blanco.traza.a_dict()
                    if estudio.organo_blanco.traza
                    else None
                ),
            )
        )

    if expediente.pbrer is not None:
        for senal in expediente.pbrer.senales:
            descripcion = (
                str(senal.descripcion.exigir()) if senal.descripcion.presente else senal.identificador
            )
            frecuencia = None
            if senal.casos is not None and senal.casos.presente:
                frecuencia = f"{senal.casos.valor.exigir()} caso(s) en el periodo"
            riesgos.append(
                RiesgoDeclarado(
                    descripcion=f"[{senal.identificador}] {descripcion}",
                    origen="Farmacovigilancia poscomercializacion (Modulo 7)",
                    frecuencia=frecuencia,
                    mitigacion_declarada=mitigacion_para(
                        f"{descripcion} "
                        + (
                            str(senal.sistema_organo.exigir())
                            if senal.sistema_organo is not None
                            and senal.sistema_organo.presente
                            else ""
                        )
                    ),
                    trazabilidad=(
                        senal.descripcion.traza.a_dict()
                        if senal.descripcion.traza
                        else None
                    ),
                )
            )
    return riesgos


def evaluar_evidencia(
    radicado: str,
    lector: ExpedienteEvidenciaPort,
    auditoria: AuditLogPort,
    momento: datetime | None = None,
) -> ResultadoEvaluacion:
    """Ejecuta la auditoria completa de los Modulos 4, 5 y 7."""
    momento = momento or datetime.now(UTC)
    auditoria.registrar(
        EventoAuditoria(
            momento=momento,
            tipo=TipoEvento.PASO_INICIADO,
            radicado=radicado,
            accion="Auditoria de evidencia cientifica (Modulos 4, 5 y 7)",
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
                accion="Contenido sospechoso en texto libre de evidencia",
                resultado=item.motivo,
                detalles={"campo": item.campo, "fragmento": item.fragmento},
            )
        )

    no_clinico = auditar_evidencia_no_clinica(
        expediente.farmacocinetica,
        expediente.toxicologia,
        expediente.reproductiva,
        expediente.especificaciones_declaradas,
    )
    ensayo = auditar_ensayo_pivotal(expediente.ensayo_pivotal)
    inmunogenicidad = auditar_inmunogenicidad(expediente.inmunogenicidad)
    pbrer = auditar_pbrer(expediente.pbrer)

    organos = tuple(
        e.organo_blanco for e in expediente.toxicologia if e.organo_blanco is not None
    )
    senales = expediente.pbrer.senales if expediente.pbrer is not None else ()
    cruce = cruzar(organos, senales, expediente.plan_riesgos)

    hallazgos: list[Hallazgo] = []
    hallazgos.extend(no_clinico.hallazgos)
    hallazgos.extend(ensayo.hallazgos)
    hallazgos.extend(inmunogenicidad.hallazgos)
    hallazgos.extend(pbrer.hallazgos)
    hallazgos.extend(cruce.hallazgos)
    hallazgos_ordenados = ordenar(hallazgos)

    insumos = armar_insumos(
        _beneficios(expediente), _riesgos(expediente), hallazgos_ordenados
    )
    resumen = consolidar(hallazgos_ordenados)

    payload = construir_payload(
        expediente=expediente,
        no_clinico=no_clinico,
        ensayo=ensayo,
        inmunogenicidad=inmunogenicidad,
        pbrer=pbrer,
        cruce=cruce,
        insumos=insumos,
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
            f"El agente ordena la evidencia; el balance y su sentido son del evaluador."
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
            accion="Auditoria de evidencia cientifica (Modulos 4, 5 y 7)",
            resultado=f"{len(hallazgos_ordenados)} hallazgos",
            detalles=resumen.a_dict(),
        )
    )

    return ResultadoEvaluacion(payload=payload, hallazgos=hallazgos_ordenados)
