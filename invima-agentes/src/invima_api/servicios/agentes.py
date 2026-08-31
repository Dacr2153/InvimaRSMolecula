"""Orquestacion de los agentes secundarios (A2, A3, A4) tras la radicacion.

El A1 corre inline: el enrutamiento depende de el. Estos tres corren en segundo
plano porque su trabajo alimenta la evaluacion, no el reparto, y encadenarlos en
la respuesta HTTP retendria al solicitante varios minutos sin razon.

Reglas de la orquestacion:

- Un agente que falla no arrastra a los demas: cada corrida esta aislada y su
  error queda escrito en el informe, visible para el evaluador.
- Un modulo ausente no es un error: el agente queda OMITIDO con la razon. Que el
  expediente no traiga Modulo 3 legible es informacion, no una excepcion.
- Nada de lo que producen es una decision. Los payloads terminan en estados
  PENDIENTE_VALIDACION_* de sus propias maquinas de estados, y este modulo no
  tiene forma de moverlos de ahi.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..config import AjustesAPI

registro = logging.getLogger("invima_api.agentes")

#: Orden de ejecucion y ficha de cada agente secundario.
AGENTES: tuple[tuple[str, str], ...] = (
    ("A2-VICR", "Validador de integridad y clasificador regulatorio (Módulo 1 legal)"),
    ("A3-ECPF", "Auditoría de calidad y procesos (Módulo 3 / CMC)"),
    ("A4-ECEF", "Auditoría de evidencia científica y clínica (Módulos 4, 5 y 7)"),
)


class AuditoriaPostgres:
    """AuditLog de los agentes hacia la tabla eventos_auditoria.

    Acepta los EventoAuditoria de cualquiera de los paquetes (a1, a2, nucleo):
    todos comparten la misma forma. Registrar es INSERT; no hay UPDATE ni DELETE.
    """

    def __init__(self, conexiones: Callable[[], Any]) -> None:
        self._conexiones = conexiones

    def registrar(self, evento: Any) -> None:
        with self._conexiones() as conexion, conexion.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO eventos_auditoria
                    (momento, radicado, tipo, accion, resultado, actor, detalles)
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    evento.momento,
                    evento.radicado,
                    str(evento.tipo),
                    evento.accion,
                    evento.resultado,
                    getattr(evento, "actor", "SISTEMA"),
                    json.dumps(getattr(evento, "detalles", {}) or {}, ensure_ascii=False, default=str),
                ),
            )
            conexion.commit()

    def eventos_de(self, radicado: str) -> tuple[Any, ...]:  # pragma: no cover
        return ()


class ExpedienteA1Postgres:
    """ExpedienteA1Port del A2 respaldado por la tabla expedientes."""

    def __init__(self, conexiones: Callable[[], Any], carpeta: Path) -> None:
        self._conexiones = conexiones
        self._carpeta = carpeta

    def cargar(self, radicado: str) -> dict[str, Any]:
        with self._conexiones() as conexion, conexion.cursor() as cursor:
            cursor.execute(
                "SELECT payload FROM expedientes WHERE radicado = %s", (radicado,)
            )
            fila = cursor.fetchone()
        if fila is None:
            raise KeyError(
                f"El radicado {radicado} no fue procesado por el A1. El A2 no "
                f"valida expedientes que no pasaron por radicacion."
            )
        return fila["payload"]

    def carpeta_dossier(self, radicado: str) -> Path:
        return self._carpeta


@dataclass(frozen=True, slots=True)
class _Contexto:
    conexiones: Callable[[], Any]
    ajustes: AjustesAPI
    radicado: str
    carpeta: Path


def _marcar(
    contexto: _Contexto,
    agente: str,
    estado: str,
    *,
    modelo: str = "",
    resumen: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
    error: str = "",
    iniciado: datetime | None = None,
) -> None:
    ahora = datetime.now(UTC)
    with contexto.conexiones() as conexion, conexion.cursor() as cursor:
        if estado == "EN_EJECUCION":
            cursor.execute(
                "UPDATE informes_agentes SET estado = %s, iniciado_en = %s "
                "WHERE radicado = %s AND agente = %s",
                (estado, ahora, contexto.radicado, agente),
            )
        else:
            duracion = int((ahora - iniciado).total_seconds() * 1000) if iniciado else None
            cursor.execute(
                """
                UPDATE informes_agentes
                   SET estado = %s, terminado_en = %s, duracion_ms = %s,
                       modelo = %s, resumen = %s::jsonb, payload = %s::jsonb,
                       error = %s
                 WHERE radicado = %s AND agente = %s
                """,
                (
                    estado,
                    ahora,
                    duracion,
                    modelo,
                    json.dumps(resumen or {}, ensure_ascii=False, default=str),
                    json.dumps(payload or {}, ensure_ascii=False, default=str),
                    error,
                    contexto.radicado,
                    agente,
                ),
            )
        conexion.commit()


def programar(conexiones: Callable[[], Any], radicado: str) -> None:
    """Deja los tres informes en PENDIENTE. La UI los ve antes de que arranquen."""
    with conexiones() as conexion, conexion.cursor() as cursor:
        for agente, nombre in AGENTES:
            cursor.execute(
                """
                INSERT INTO informes_agentes (radicado, agente, nombre, estado)
                VALUES (%s, %s, %s, 'PENDIENTE')
                ON CONFLICT (radicado, agente) DO UPDATE
                    SET estado = 'PENDIENTE', error = '', payload = '{}'::jsonb,
                        resumen = '{}'::jsonb, iniciado_en = NULL, terminado_en = NULL
                """,
                (radicado, agente, nombre),
            )
        conexion.commit()


# -------------------------------------------------------------------- resumen


def _contar_severidades(hallazgos: list[dict[str, Any]], clave: str) -> dict[str, int]:
    conteo: dict[str, int] = {}
    for h in hallazgos:
        severidad = str(h.get(clave, "SIN_SEVERIDAD"))
        conteo[severidad] = conteo.get(severidad, 0) + 1
    return conteo


def _resumen_a2(payload: dict[str, Any]) -> dict[str, Any]:
    dictamen = payload.get("dictamen") or {}
    alertas = payload.get("alertas") or []
    return {
        "estado_dictamen": dictamen.get("estado"),
        "severidad_maxima": dictamen.get("severidad_maxima"),
        "retiene_reparto": dictamen.get("retiene_reparto", False),
        "hallazgos": len(alertas),
        "por_severidad": _contar_severidades(alertas, "severidad"),
        "clasificacion": (payload.get("clasificacion_taxonomica") or {})
        .get("dimension_producto", {})
        .get("valor"),
    }


def _resumen_nucleo(payload: dict[str, Any]) -> dict[str, Any]:
    hallazgos = payload.get("hallazgos") or []
    resumen = payload.get("resumen") or {}
    plano: dict[str, Any] = {
        "hallazgos": len(hallazgos),
        "por_severidad": _contar_severidades(hallazgos, "severidad"),
    }
    cobertura = resumen.get("cobertura_verificable")
    if isinstance(cobertura, dict):
        plano["cobertura_verificable"] = cobertura.get("valor")
    sospechoso = payload.get("contenido_sospechoso") or []
    if sospechoso:
        plano["contenido_sospechoso"] = len(sospechoso)
    return plano


# -------------------------------------------------------------------- agentes


def _correr_a2(contexto: _Contexto) -> tuple[dict[str, Any], dict[str, Any], str]:
    from invima_a1.adaptadores.salida.parser_fake import ParserSidecarMarkdown
    from invima_a2.adaptadores.salida.extractor_legal_fake import (
        ExtractorLegalDeterminista,
    )
    from invima_a2.aplicacion.validar_y_clasificar import (
        Dependencias,
        ValidarYClasificarUseCase,
    )

    if contexto.ajustes.offline:
        extractor: Any = ExtractorLegalDeterminista()
    else:
        import os

        from invima_a1.adaptadores.salida.extractor_gemini import ExtractorGemini

        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            extractor = ExtractorLegalDeterminista()
        else:
            extractor = ExtractorGemini(
                api_key=api_key,
                modelo=os.getenv("INVIMA_MODELO", "gemini-flash-latest"),
            )

    deps = Dependencias(
        expediente_a1=ExpedienteA1Postgres(contexto.conexiones, contexto.carpeta),
        parser=ParserSidecarMarkdown(),
        extractor=extractor,
        auditoria=AuditoriaPostgres(contexto.conexiones),
    )
    resultado = ValidarYClasificarUseCase(deps).ejecutar(contexto.radicado)
    return resultado.payload, _resumen_a2(resultado.payload), extractor.identificador_modelo


def _correr_a3(contexto: _Contexto) -> tuple[dict[str, Any], dict[str, Any], str]:
    from invima_a3.adaptadores.salida.expediente_calidad_markdown import (
        LectorModulo3Markdown,
    )
    from invima_a3.aplicacion.auditar_calidad import auditar_calidad
    from invima_a3.config import SinEspecificacionesNormativas

    ruta = contexto.carpeta / "modulo3_calidad.md"
    if not ruta.exists():
        raise _Omitido(
            "El expediente no trae un Modulo 3 legible (falta modulo3_calidad.md). "
            "Sin el modulo de calidad no hay nada que auditar."
        )
    resultado = auditar_calidad(
        radicado=contexto.radicado,
        lector=LectorModulo3Markdown(ruta),
        auditoria=AuditoriaPostgres(contexto.conexiones),
    )
    return resultado.payload, _resumen_nucleo(resultado.payload), "motores deterministas (sin LLM)"


def _correr_a4(contexto: _Contexto) -> tuple[dict[str, Any], dict[str, Any], str]:
    from invima_a4.adaptadores.salida.expediente_evidencia_markdown import (
        LectorEvidenciaMarkdown,
    )
    from invima_a4.aplicacion.evaluar_evidencia import evaluar_evidencia

    combinado = contexto.carpeta / "modulo45_evidencia.md"
    if not combinado.exists():
        # Los folios se extraen por separado; el A4 lee un solo expediente de
        # evidencia, asi que se concatenan en orden de modulo.
        partes: list[str] = []
        for nombre in ("modulo4_evidencia.md", "modulo5_evidencia.md", "modulo7_pgr.md"):
            candidato = contexto.carpeta / nombre
            if candidato.exists():
                partes.append(candidato.read_text(encoding="utf-8"))
        if not partes:
            raise _Omitido(
                "El expediente no trae Modulos 4, 5 ni 7 legibles. Sin evidencia "
                "no clinica ni clinica no hay nada que auditar."
            )
        combinado.write_text("\n\n".join(partes), encoding="utf-8")

    resultado = evaluar_evidencia(
        radicado=contexto.radicado,
        lector=LectorEvidenciaMarkdown(combinado),
        auditoria=AuditoriaPostgres(contexto.conexiones),
    )
    return resultado.payload, _resumen_nucleo(resultado.payload), "motores deterministas (sin LLM)"


class _Omitido(Exception):
    """El expediente no trae el modulo que este agente audita."""


_CORREDORES: dict[str, Callable[[_Contexto], tuple[dict[str, Any], dict[str, Any], str]]] = {
    "A2-VICR": _correr_a2,
    "A3-ECPF": _correr_a3,
    "A4-ECEF": _correr_a4,
}


def ejecutar_agentes(
    conexiones: Callable[[], Any],
    ajustes: AjustesAPI,
    radicado: str,
    carpeta: Path,
) -> None:
    """Corre A2, A3 y A4 en secuencia, cada uno aislado del resto.

    Pensada para BackgroundTasks de FastAPI: no lanza jamas. Todo desenlace,
    incluido un crash, termina escrito en informes_agentes.
    """
    contexto = _Contexto(
        conexiones=conexiones, ajustes=ajustes, radicado=radicado, carpeta=carpeta
    )
    for agente, _nombre in AGENTES:
        inicio = datetime.now(UTC)
        _marcar(contexto, agente, "EN_EJECUCION")
        try:
            payload, resumen, modelo = _CORREDORES[agente](contexto)
        except _Omitido as razon:
            registro.info("%s omitido en %s: %s", agente, radicado, razon)
            _marcar(
                contexto,
                agente,
                "OMITIDO",
                error=str(razon),
                iniciado=inicio,
            )
        except Exception as error:  # noqa: BLE001 - el informe es el canal del error
            registro.exception("%s fallo en %s", agente, radicado)
            _marcar(
                contexto,
                agente,
                "ERROR",
                error=f"{type(error).__name__}: {error}",
                iniciado=inicio,
            )
        else:
            _marcar(
                contexto,
                agente,
                "COMPLETADO",
                modelo=modelo,
                resumen=resumen,
                payload=payload,
                iniciado=inicio,
            )


__all__ = ["AGENTES", "ejecutar_agentes", "programar"]
