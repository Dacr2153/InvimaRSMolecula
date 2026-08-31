"""Router de evaluacion: lo que ve y hace el servidor publico competente.

La regla que ordena este modulo: el unico endpoint que cambia el estado del
expediente es POST /decision, y exige un usuario con nombre. La transicion no
se escribe a mano en SQL: se delega en la maquina de estados del dominio, de
modo que la API no puede saltarse la barrera del art. 7.1 aunque alguien lo
intente desde aqui.
"""

from __future__ import annotations

import json

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from invima_a1.domain.errores import TransicionIlegalError
from invima_a1.domain.estados import (
    DecisionHumana,
    EstadoExpediente,
    SentidoDecision,
    validar_transicion,
)

from ..esquemas import (
    ActualizarItemChecklist,
    Consulta,
    ConsultaSugerida,
    CrearConsulta,
    CrearItemChecklist,
    DecisionHumanaVista,
    DocumentoExpediente,
    EventoVista,
    ExpedienteDetalle,
    FuenteExterna,
    InformeAgente,
    ItemBandeja,
    ItemChecklist,
    RespuestaDecision,
    SolicitudDecision,
    VincularFuente,
)
from ..servicios.consultas import buscar_en_corpus
from .comun import ESTADOS_DECIDIBLES, etiqueta_estado, obtener_pool

router = APIRouter(tags=["evaluacion"])


# ------------------------------------------------------------------- lectura


def _dato(payload: dict[str, Any], bloque: str, campo: str) -> str:
    """Extrae el valor de un Dato[T] del payload del A1.

    Cada campo del payload es {valor, origen, trazabilidad}. Aqui solo se toma
    el valor para listar; la procedencia completa viaja intacta en `payload`
    para que la interfaz la muestre junto al dato.
    """
    entrada = (payload.get(bloque) or {}).get(campo)
    if isinstance(entrada, dict):
        valor = entrada.get("valor")
        return "" if valor is None else str(valor)
    return ""


def _ruta_recomendada(payload: dict[str, Any]) -> str:
    enrutamiento = payload.get("enrutamiento") or {}
    ruta = enrutamiento.get("ruta_recomendada") or {}
    valor = ruta.get("valor") if isinstance(ruta, dict) else None
    return "" if valor is None else str(valor)


def _dias_en_cola(fecha_radicacion: date) -> int:
    return max(0, (datetime.now(UTC).date() - fecha_radicacion).days)


def _fila_expediente(cursor: Any, radicado: str) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT e.radicado, e.fecha_radicacion, e.estado, e.decision_humana,
               e.eventos, e.payload, e.solicitud_id,
               COALESCE(t.etiqueta, '') AS tramite
          FROM expedientes e
          LEFT JOIN solicitudes s ON s.id = e.solicitud_id
          LEFT JOIN tipos_tramite t ON t.id = s.tipo_tramite
         WHERE e.radicado = %s
        """,
        (radicado,),
    )
    fila = cursor.fetchone()
    if fila is None:
        raise HTTPException(status_code=404, detail=f"No existe el expediente {radicado}")
    return fila


@router.get("/expedientes", response_model=list[ItemBandeja])
def listar_expedientes(pool: Any = Depends(obtener_pool)) -> list[ItemBandeja]:
    """Bandeja del evaluador. Los pendientes primero: son los que esperan a una persona."""
    with pool.connection() as conexion, conexion.cursor() as cursor:
        cursor.execute(
            """
            SELECT e.radicado, e.fecha_radicacion, e.estado, e.payload,
                   COALESCE(t.etiqueta, '') AS tramite
              FROM expedientes e
              LEFT JOIN solicitudes s ON s.id = e.solicitud_id
              LEFT JOIN tipos_tramite t ON t.id = s.tipo_tramite
             ORDER BY
               (e.estado = 'PENDIENTE_VALIDACION_HUMANA') DESC,
               e.fecha_radicacion ASC,
               e.radicado ASC
            """
        )
        filas = cursor.fetchall()

    return [
        ItemBandeja(
            radicado=f["radicado"],
            producto=_dato(f["payload"], "producto", "nombre"),
            principio_activo=_dato(f["payload"], "producto", "principio_activo"),
            titular=_dato(f["payload"], "solicitante", "nombre_titular"),
            tramite=f["tramite"],
            estado=f["estado"],
            estado_label=etiqueta_estado(f["estado"]),
            dias_en_cola=_dias_en_cola(f["fecha_radicacion"]),
            ruta_recomendada=_ruta_recomendada(f["payload"]),
        )
        for f in filas
    ]


@router.get("/expedientes/{radicado}", response_model=ExpedienteDetalle)
def leer_expediente(
    radicado: str, pool: Any = Depends(obtener_pool)
) -> ExpedienteDetalle:
    with pool.connection() as conexion, conexion.cursor() as cursor:
        fila = _fila_expediente(cursor, radicado)
        cursor.execute(
            """
            SELECT d.requerido_id, r.nombre, r.modulo_id AS modulo,
                   d.nombre_archivo, d.tamano_bytes, d.sha256, d.cargado_en
              FROM documentos_cargados d
              JOIN documentos_requeridos r ON r.id = d.requerido_id
             WHERE d.solicitud_id = %s
             ORDER BY r.orden, r.id
            """,
            (fila["solicitud_id"],),
        )
        documentos = cursor.fetchall()

    payload = fila["payload"] or {}
    decision = fila["decision_humana"]

    return ExpedienteDetalle(
        radicado=fila["radicado"],
        estado=fila["estado"],
        estado_label=etiqueta_estado(fila["estado"]),
        producto=_dato(payload, "producto", "nombre"),
        principio_activo=_dato(payload, "producto", "principio_activo"),
        titular=_dato(payload, "solicitante", "nombre_titular"),
        tramite=fila["tramite"],
        fecha_radicacion=fila["fecha_radicacion"],
        payload=payload,
        documentos=[DocumentoExpediente(**d) for d in documentos],
        decision_humana=(
            DecisionHumanaVista(
                usuario=decision["usuario"],
                sentido=decision["sentido"],
                momento=decision["momento"],
                observaciones=decision.get("observaciones", ""),
            )
            if decision
            else None
        ),
        puede_decidir=fila["estado"] in ESTADOS_DECIDIBLES,
        eventos=[
            EventoVista(
                momento=e["timestamp"],
                tipo=e["tipo"],
                accion=e["accion"],
                resultado=e["resultado"],
                actor=e.get("actor", "SISTEMA"),
            )
            for e in (fila["eventos"] or [])
        ],
    )


# ------------------------------------------------------------------ decision

_SENTIDOS = {s.value for s in SentidoDecision}


@router.post("/expedientes/{radicado}/decision", response_model=RespuestaDecision)
def registrar_decision(
    radicado: str,
    cuerpo: SolicitudDecision,
    pool: Any = Depends(obtener_pool),
) -> RespuestaDecision:
    """Unico punto del sistema que saca un expediente del gate humano.

    La validacion no se reimplementa aqui: se construye el DecisionHumana del
    dominio y se consulta validar_transicion. Si el estado no admite decision, o
    si el usuario viene vacio, el propio dominio lo rechaza.
    """
    if cuerpo.sentido not in _SENTIDOS:
        raise HTTPException(
            status_code=422,
            detail=f"Sentido no valido: {cuerpo.sentido}. Use uno de {sorted(_SENTIDOS)}.",
        )

    momento = datetime.now(UTC)
    try:
        decision = DecisionHumana(
            usuario=cuerpo.usuario,
            sentido=SentidoDecision(cuerpo.sentido),
            momento=momento,
            observaciones=cuerpo.observaciones,
            campos_corregidos=tuple(cuerpo.campos_corregidos),
        )
    except TransicionIlegalError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    with pool.connection() as conexion, conexion.cursor() as cursor:
        cursor.execute(
            "SELECT estado, payload, eventos FROM expedientes "
            "WHERE radicado = %s FOR UPDATE",
            (radicado,),
        )
        fila = cursor.fetchone()
        if fila is None:
            raise HTTPException(status_code=404, detail=f"No existe el expediente {radicado}")

        origen = EstadoExpediente(fila["estado"])
        destino = decision.estado_resultante
        try:
            validar_transicion(origen, destino, decision)
        except TransicionIlegalError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

        eventos = list(fila["eventos"] or [])
        for tipo, accion, resultado in (
            (
                "DECISION_HUMANA",
                f"Decision del evaluador: {decision.sentido}",
                decision.observaciones or "Sin observaciones",
            ),
            ("CAMBIO_ESTADO", f"Transicion {origen} -> {destino}", "Aplicada"),
        ):
            eventos.append(
                {
                    "timestamp": momento.isoformat(),
                    "tipo": tipo,
                    "radicado": radicado,
                    "accion": accion,
                    "resultado": resultado,
                    "actor": decision.usuario,
                    "detalles": {"campos_corregidos": list(decision.campos_corregidos)},
                }
            )
            cursor.execute(
                """
                INSERT INTO eventos_auditoria
                    (momento, radicado, tipo, accion, resultado, actor, detalles)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    momento,
                    radicado,
                    tipo,
                    accion,
                    resultado,
                    decision.usuario,
                    "{}",
                ),
            )

        payload = dict(fila["payload"] or {})
        supervision = dict(payload.get("supervision_humana") or {})
        supervision.update(
            {
                "estado": f"DECIDIDO POR EL EVALUADOR ({decision.sentido})",
                "usuario_responsable": decision.usuario,
                "sentido_decision": str(decision.sentido),
                "firma_timestamp": momento.isoformat(),
                "campos_corregidos": list(decision.campos_corregidos),
                "observaciones": decision.observaciones,
                "checklist_evaluador": {
                    "datos_extraidos_validados": True,
                    "busqueda_internacional_confirmada": True,
                    "enrutamiento_aprobado": decision.sentido
                    is not SentidoDecision.DEVOLVER,
                },
            }
        )
        payload["supervision_humana"] = supervision
        if isinstance(payload.get("radicacion"), dict):
            payload["radicacion"]["estado"] = str(destino)

        cursor.execute(
            """
            UPDATE expedientes
               SET estado = %s,
                   decision_humana = %s::jsonb,
                   eventos = %s::jsonb,
                   payload = %s::jsonb,
                   actualizado_en = now()
             WHERE radicado = %s
            """,
            (
                str(destino),
                json.dumps(
                    {
                        "usuario": decision.usuario,
                        "sentido": str(decision.sentido),
                        "momento": momento.isoformat(),
                        "observaciones": decision.observaciones,
                        "campos_corregidos": list(decision.campos_corregidos),
                    },
                    ensure_ascii=False,
                ),
                json.dumps(eventos, ensure_ascii=False),
                json.dumps(payload, ensure_ascii=False),
                radicado,
            ),
        )

    return RespuestaDecision(
        estado=str(destino),
        usuario_responsable=decision.usuario,
        sentido=str(decision.sentido),
        firma_timestamp=momento,
    )


# ------------------------------------------------------------------- agentes


@router.get("/expedientes/{radicado}/agentes", response_model=list[InformeAgente])
def leer_informes_agentes(
    radicado: str, pool: Any = Depends(obtener_pool)
) -> list[InformeAgente]:
    """El trabajo de los cuatro agentes sobre este expediente.

    El A1 no vive en informes_agentes porque corre inline durante la radicacion:
    su informe ES el payload del expediente. Aqui se le da la misma forma que a
    los demas para que el evaluador vea un solo tablero.
    """
    with pool.connection() as conexion, conexion.cursor() as cursor:
        fila = _fila_expediente(cursor, radicado)
        cursor.execute(
            "SELECT agente, nombre, estado, iniciado_en, terminado_en, duracion_ms, "
            "modelo, resumen, payload, error FROM informes_agentes "
            "WHERE radicado = %s ORDER BY agente",
            (radicado,),
        )
        secundarios = cursor.fetchall()

    payload_a1 = fila["payload"] or {}
    seguridad = payload_a1.get("seguridad_y_trazabilidad") or {}
    eventos_a1 = seguridad.get("auditoria_log") or []
    normativa = payload_a1.get("evaluacion_normativa") or {}
    enrutamiento = payload_a1.get("enrutamiento") or {}
    sospechoso = seguridad.get("contenido_sospechoso_detectado") or []

    resumen_a1: dict[str, Any] = {
        "estatus_molecula": (normativa.get("estatus_molecula") or {}).get("valor"),
        "ruta_recomendada": (enrutamiento.get("ruta_recomendada") or {}).get("valor"),
        "eventos_auditoria": len(eventos_a1),
        "consultas_externas": sum(
            1 for e in eventos_a1 if e.get("tipo") == "CONSULTA_EXTERNA"
        ),
    }
    if sospechoso:
        resumen_a1["contenido_sospechoso"] = len(sospechoso)

    informe_a1 = InformeAgente(
        agente="A1-RCE",
        nombre="Receptor, clasificador y enrutador (Módulo 1 administrativo)",
        estado="COMPLETADO",
        iniciado_en=None,
        terminado_en=None,
        duracion_ms=None,
        modelo=seguridad.get("modelo_utilizado", ""),
        resumen=resumen_a1,
        payload=payload_a1,
    )

    return [informe_a1] + [InformeAgente(**f) for f in secundarios]


# ----------------------------------------------------------------- checklist


def _checklist(cursor: Any, radicado: str) -> list[ItemChecklist]:
    cursor.execute(
        "SELECT id, texto, verificado, origen, orden, verificado_por, verificado_en "
        "FROM checklist_items WHERE radicado = %s ORDER BY orden, creado_en",
        (radicado,),
    )
    return [ItemChecklist(**f) for f in cursor.fetchall()]


@router.get("/expedientes/{radicado}/checklist", response_model=list[ItemChecklist])
def leer_checklist(radicado: str, pool: Any = Depends(obtener_pool)) -> list[ItemChecklist]:
    with pool.connection() as conexion, conexion.cursor() as cursor:
        _fila_expediente(cursor, radicado)
        return _checklist(cursor, radicado)


@router.post("/expedientes/{radicado}/checklist", response_model=ItemChecklist, status_code=201)
def crear_item_checklist(
    radicado: str, cuerpo: CrearItemChecklist, pool: Any = Depends(obtener_pool)
) -> ItemChecklist:
    texto = cuerpo.texto.strip()
    if not texto:
        raise HTTPException(status_code=422, detail="El texto del item no puede estar vacio")

    with pool.connection() as conexion, conexion.cursor() as cursor:
        _fila_expediente(cursor, radicado)
        cursor.execute(
            """
            INSERT INTO checklist_items (radicado, texto, origen, orden)
            VALUES (
                %s, %s, 'EVALUADOR',
                COALESCE((SELECT MAX(orden) + 1 FROM checklist_items WHERE radicado = %s), 0)
            )
            RETURNING id, texto, verificado, origen, orden, verificado_por, verificado_en
            """,
            (radicado, texto, radicado),
        )
        return ItemChecklist(**cursor.fetchone())


@router.patch("/expedientes/{radicado}/checklist/{item_id}", response_model=ItemChecklist)
def marcar_item_checklist(
    radicado: str,
    item_id: UUID,
    cuerpo: ActualizarItemChecklist,
    pool: Any = Depends(obtener_pool),
) -> ItemChecklist:
    """Verificar un item deja constancia de quien lo hizo y cuando."""
    if not cuerpo.usuario.strip():
        raise HTTPException(
            status_code=422,
            detail="Verificar un item del checklist requiere identificar al evaluador",
        )

    with pool.connection() as conexion, conexion.cursor() as cursor:
        cursor.execute(
            """
            UPDATE checklist_items
               SET verificado = %s,
                   verificado_por = CASE WHEN %s THEN %s ELSE NULL END,
                   verificado_en  = CASE WHEN %s THEN now() ELSE NULL END
             WHERE id = %s AND radicado = %s
            RETURNING id, texto, verificado, origen, orden, verificado_por, verificado_en
            """,
            (
                cuerpo.verificado,
                cuerpo.verificado,
                cuerpo.usuario.strip(),
                cuerpo.verificado,
                item_id,
                radicado,
            ),
        )
        fila = cursor.fetchone()
        if fila is None:
            raise HTTPException(status_code=404, detail="No existe ese item en el expediente")
        return ItemChecklist(**fila)


@router.delete("/expedientes/{radicado}/checklist/{item_id}", status_code=204)
def eliminar_item_checklist(
    radicado: str, item_id: UUID, pool: Any = Depends(obtener_pool)
) -> None:
    """Solo se borra lo que agrego un evaluador. La plantilla es el minimo exigible."""
    with pool.connection() as conexion, conexion.cursor() as cursor:
        cursor.execute(
            "SELECT origen FROM checklist_items WHERE id = %s AND radicado = %s",
            (item_id, radicado),
        )
        fila = cursor.fetchone()
        if fila is None:
            raise HTTPException(status_code=404, detail="No existe ese item en el expediente")
        if fila["origen"] != "EVALUADOR":
            raise HTTPException(
                status_code=409,
                detail="Solo pueden eliminarse los items agregados por el evaluador",
            )
        cursor.execute("DELETE FROM checklist_items WHERE id = %s", (item_id,))


# ------------------------------------------------------------------- fuentes


@router.get("/expedientes/{radicado}/fuentes", response_model=list[FuenteExterna])
def leer_fuentes(radicado: str, pool: Any = Depends(obtener_pool)) -> list[FuenteExterna]:
    with pool.connection() as conexion, conexion.cursor() as cursor:
        _fila_expediente(cursor, radicado)
        cursor.execute(
            "SELECT id, fuente, titulo, tipo, pais, fecha, url, encontrada, "
            "observaciones, vinculada FROM fuentes_externas "
            "WHERE radicado = %s ORDER BY fuente, titulo",
            (radicado,),
        )
        return [FuenteExterna(**f) for f in cursor.fetchall()]


@router.post("/expedientes/{radicado}/fuentes/{fuente_id}/vinculo", response_model=FuenteExterna)
def vincular_fuente(
    radicado: str,
    fuente_id: UUID,
    cuerpo: VincularFuente,
    pool: Any = Depends(obtener_pool),
) -> FuenteExterna:
    """Vincular una fuente es un acto del evaluador: queda con su nombre.

    El agente encontro la fuente; que sea pertinente para ESTE expediente lo
    decide una persona.
    """
    if not cuerpo.usuario.strip():
        raise HTTPException(
            status_code=422, detail="Vincular una fuente requiere identificar al evaluador"
        )

    with pool.connection() as conexion, conexion.cursor() as cursor:
        cursor.execute(
            """
            UPDATE fuentes_externas
               SET vinculada = %s,
                   vinculada_por = CASE WHEN %s THEN %s ELSE NULL END,
                   vinculada_en  = CASE WHEN %s THEN now() ELSE NULL END
             WHERE id = %s AND radicado = %s
            RETURNING id, fuente, titulo, tipo, pais, fecha, url, encontrada,
                      observaciones, vinculada
            """,
            (
                cuerpo.vinculada,
                cuerpo.vinculada,
                cuerpo.usuario.strip(),
                cuerpo.vinculada,
                fuente_id,
                radicado,
            ),
        )
        fila = cursor.fetchone()
        if fila is None:
            raise HTTPException(status_code=404, detail="No existe esa fuente en el expediente")
        return FuenteExterna(**fila)


# ------------------------------------------------------------------ consultas


@router.get("/consultas/sugeridas", response_model=list[ConsultaSugerida])
def leer_consultas_sugeridas(pool: Any = Depends(obtener_pool)) -> list[ConsultaSugerida]:
    with pool.connection() as conexion, conexion.cursor() as cursor:
        cursor.execute(
            "SELECT id, pregunta FROM corpus_normativo WHERE sugerida ORDER BY orden, id"
        )
        return [ConsultaSugerida(**f) for f in cursor.fetchall()]


@router.get("/expedientes/{radicado}/consultas", response_model=list[Consulta])
def leer_consultas(radicado: str, pool: Any = Depends(obtener_pool)) -> list[Consulta]:
    with pool.connection() as conexion, conexion.cursor() as cursor:
        _fila_expediente(cursor, radicado)
        cursor.execute(
            "SELECT id, pregunta, respuesta, cita, url, encontrada, momento "
            "FROM consultas WHERE radicado = %s ORDER BY momento",
            (radicado,),
        )
        return [Consulta(**f) for f in cursor.fetchall()]


@router.post("/expedientes/{radicado}/consultas", response_model=Consulta, status_code=201)
def crear_consulta(
    radicado: str, cuerpo: CrearConsulta, pool: Any = Depends(obtener_pool)
) -> Consulta:
    """Consulta al corpus normativo.

    Cuando no hay coincidencia se responde que no la hay, con `encontrada` en
    falso. No se redacta una respuesta plausible: una cita inventada sobre norma
    farmacologica es peor que un "no se encontro".
    """
    pregunta = cuerpo.pregunta.strip()
    if not pregunta:
        raise HTTPException(status_code=422, detail="La pregunta no puede estar vacia")

    with pool.connection() as conexion, conexion.cursor() as cursor:
        _fila_expediente(cursor, radicado)
        cursor.execute(
            "SELECT id, pregunta, respuesta, cita, url, etiquetas FROM corpus_normativo"
        )
        entrada = buscar_en_corpus(pregunta, cursor.fetchall())

        cursor.execute(
            """
            INSERT INTO consultas
                (radicado, usuario, pregunta, respuesta, cita, url, encontrada)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id, pregunta, respuesta, cita, url, encontrada, momento
            """,
            (
                radicado,
                cuerpo.usuario.strip(),
                pregunta,
                entrada["respuesta"],
                entrada["cita"],
                entrada["url"],
                entrada["encontrada"],
            ),
        )
        return Consulta(**cursor.fetchone())
