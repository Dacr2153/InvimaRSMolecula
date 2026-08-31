"""Zona de radicacion: el wizard del solicitante.

Todo lo de aqui es mutable hasta que se radica. Al radicar, la solicitud se
congela y nace el expediente, que ya no se toca por esta via.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
)

from ..config import AjustesAPI
from ..esquemas import (
    CrearEnlace,
    EnlaceEvidencia,
    ActualizarSolicitud,
    CrearSolicitud,
    DocumentoSolicitud,
    ResultadoRadicacion,
    Solicitud,
)
from ..servicios.agentes import ejecutar_agentes, programar
from ..servicios.demo import sembrar_borrador
from ..servicios.enlaces import EnlaceInvalido, clasificar
from ..servicios.radicar import ErrorRadicacion, radicar_solicitud, sha256_de
from .comun import obtener_ajustes, obtener_pool

router = APIRouter(prefix="/solicitudes", tags=["radicacion"])

_COLUMNAS = (
    "id, estado, tipo_tramite, tipo_producto, datos_declarados, tarifa_codigo, "
    "metodo_pago, comprobante, valor_pagado, fecha_pago, radicado, radicada_en"
)

#: Columnas que el PATCH puede tocar. Lista blanca: el nombre de columna entra
#: al SQL, asi que no puede venir del cliente sin filtrar.
_CAMPOS_EDITABLES = frozenset(
    {
        "tipo_tramite",
        "tipo_producto",
        "datos_declarados",
        "tarifa_codigo",
        "metodo_pago",
        "comprobante",
        "valor_pagado",
        "fecha_pago",
    }
)


def _documentos(cursor: Any, solicitud_id: UUID) -> list[DocumentoSolicitud]:
    cursor.execute(
        """
        SELECT requerido_id, nombre_archivo, tamano_bytes, sha256, cargado_en
          FROM documentos_cargados
         WHERE solicitud_id = %s
         ORDER BY cargado_en
        """,
        (str(solicitud_id),),
    )
    return [DocumentoSolicitud(**fila) for fila in cursor.fetchall()]


def _enlaces(cursor: Any, solicitud_id: UUID) -> list[EnlaceEvidencia]:
    cursor.execute(
        "SELECT id, url, titulo, tipo, referencia, creado_en FROM enlaces_evidencia "
        "WHERE solicitud_id = %s ORDER BY creado_en",
        (str(solicitud_id),),
    )
    return [EnlaceEvidencia(**f) for f in cursor.fetchall()]


def _leer(cursor: Any, solicitud_id: UUID) -> Solicitud:
    cursor.execute(
        f"SELECT {_COLUMNAS} FROM solicitudes WHERE id = %s", (str(solicitud_id),)
    )
    fila = cursor.fetchone()
    if fila is None:
        raise HTTPException(404, f"No existe la solicitud {solicitud_id}")
    return Solicitud(
        **fila,
        documentos=_documentos(cursor, solicitud_id),
        enlaces=_enlaces(cursor, solicitud_id),
    )


def _exigir_borrador(cursor: Any, solicitud_id: UUID) -> None:
    cursor.execute(
        "SELECT estado FROM solicitudes WHERE id = %s FOR UPDATE", (str(solicitud_id),)
    )
    fila = cursor.fetchone()
    if fila is None:
        raise HTTPException(404, f"No existe la solicitud {solicitud_id}")
    if fila["estado"] != "BORRADOR":
        raise HTTPException(
            409,
            f"La solicitud esta en estado {fila['estado']} y ya no admite cambios",
        )


@router.post("", response_model=Solicitud, status_code=201)
def crear_solicitud(
    cuerpo: CrearSolicitud | None = None,
    pool: Any = Depends(obtener_pool),
    ajustes: AjustesAPI = Depends(obtener_ajustes),
) -> Solicitud:
    """Abre una solicitud en BORRADOR.

    Sin `solicitanteNit` se usa el solicitante sembrado de demostracion. En
    produccion esto lo daria la sesion autenticada; el contrato no define
    autenticacion todavia y no se inventa una aqui.
    """
    nit = cuerpo.solicitante_nit if cuerpo else None
    with pool.connection() as conexion, conexion.cursor() as cursor:
        if nit:
            cursor.execute("SELECT id FROM solicitantes WHERE nit = %s", (nit,))
        else:
            cursor.execute("SELECT id FROM solicitantes ORDER BY creado_en LIMIT 1")
        fila = cursor.fetchone()
        if fila is None:
            raise HTTPException(
                404, f"No hay un solicitante registrado con el NIT {nit}" if nit
                else "No hay solicitantes registrados en la base",
            )

        cursor.execute(
            "INSERT INTO solicitudes (solicitante_id) VALUES (%s) RETURNING id",
            (fila["id"],),
        )
        nueva = cursor.fetchone()["id"]
        if ajustes.demo:
            sembrar_borrador(
                cursor,
                nueva,
                ajustes.directorio_demo,
                ajustes.directorio_datos,
                sha256_de,
            )
        solicitud = _leer(cursor, nueva)
        conexion.commit()
    return solicitud


@router.get("/{solicitud_id}", response_model=Solicitud)
def leer_solicitud(solicitud_id: UUID, pool: Any = Depends(obtener_pool)) -> Solicitud:
    with pool.connection() as conexion, conexion.cursor() as cursor:
        return _leer(cursor, solicitud_id)


@router.patch("/{solicitud_id}", response_model=Solicitud)
def actualizar_solicitud(
    solicitud_id: UUID,
    cuerpo: ActualizarSolicitud,
    pool: Any = Depends(obtener_pool),
) -> Solicitud:
    cambios = cuerpo.model_dump(exclude_unset=True, by_alias=False)
    cambios = {k: v for k, v in cambios.items() if k in _CAMPOS_EDITABLES}

    with pool.connection() as conexion, conexion.cursor() as cursor:
        _exigir_borrador(cursor, solicitud_id)
        if cambios:
            from psycopg.types.json import Jsonb

            if "datos_declarados" in cambios:
                cambios["datos_declarados"] = Jsonb(cambios["datos_declarados"] or {})
            asignaciones = ", ".join(f"{campo} = %({campo})s" for campo in cambios)
            cursor.execute(
                f"UPDATE solicitudes SET {asignaciones}, actualizada_en = now() "
                f"WHERE id = %(id)s",
                {**cambios, "id": str(solicitud_id)},
            )
        solicitud = _leer(cursor, solicitud_id)
        conexion.commit()
    return solicitud


@router.post("/{solicitud_id}/documentos/{requerido_id}", response_model=DocumentoSolicitud)
async def cargar_documento(
    solicitud_id: UUID,
    requerido_id: str,
    file: UploadFile = File(...),
    pool: Any = Depends(obtener_pool),
    ajustes: AjustesAPI = Depends(obtener_ajustes),
) -> DocumentoSolicitud:
    """Recibe un folio y lo guarda con su huella SHA-256.

    La huella permite probar anos despues que lo que se evaluo es byte por byte
    lo que se radico.
    """
    nombre_archivo = Path(file.filename or "documento").name
    extension = Path(nombre_archivo).suffix.lower()
    if extension not in ajustes.extensiones_permitidas:
        raise HTTPException(
            415,
            f"Extension no permitida: {extension or '(sin extension)'}. "
            f"Se aceptan {', '.join(sorted(ajustes.extensiones_permitidas))}",
        )

    contenido = bytearray()
    while fragmento := await file.read(1024 * 1024):
        contenido.extend(fragmento)
        if len(contenido) > ajustes.tamano_maximo_bytes:
            raise HTTPException(
                413,
                f"El archivo supera el maximo de "
                f"{ajustes.tamano_maximo_bytes // (1024 * 1024)} MB",
            )
    if not contenido:
        raise HTTPException(422, "El archivo llego vacio")

    datos = bytes(contenido)
    huella = sha256_de(datos)
    relativo = Path("cargas") / str(solicitud_id) / f"{requerido_id}{extension}"
    destino = ajustes.directorio_datos / relativo

    with pool.connection() as conexion, conexion.cursor() as cursor:
        _exigir_borrador(cursor, solicitud_id)
        cursor.execute(
            "SELECT id FROM documentos_requeridos WHERE id = %s", (requerido_id,)
        )
        if cursor.fetchone() is None:
            raise HTTPException(404, f"No existe el documento requerido {requerido_id}")

        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(datos)

        cursor.execute(
            """
            INSERT INTO documentos_cargados
                (solicitud_id, requerido_id, nombre_archivo, ruta_relativa,
                 tamano_bytes, tipo_mime, sha256)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (solicitud_id, requerido_id) DO UPDATE SET
                nombre_archivo = EXCLUDED.nombre_archivo,
                ruta_relativa  = EXCLUDED.ruta_relativa,
                tamano_bytes   = EXCLUDED.tamano_bytes,
                tipo_mime      = EXCLUDED.tipo_mime,
                sha256         = EXCLUDED.sha256,
                cargado_en     = now()
            RETURNING requerido_id, nombre_archivo, tamano_bytes, sha256, cargado_en
            """,
            (
                str(solicitud_id),
                requerido_id,
                nombre_archivo,
                str(relativo),
                len(datos),
                file.content_type or "application/octet-stream",
                huella,
            ),
        )
        fila = cursor.fetchone()
        conexion.commit()
    return DocumentoSolicitud(**fila)


@router.delete("/{solicitud_id}/documentos/{requerido_id}", status_code=204)
def eliminar_documento(
    solicitud_id: UUID,
    requerido_id: str,
    pool: Any = Depends(obtener_pool),
    ajustes: AjustesAPI = Depends(obtener_ajustes),
) -> Response:
    with pool.connection() as conexion, conexion.cursor() as cursor:
        _exigir_borrador(cursor, solicitud_id)
        cursor.execute(
            """
            DELETE FROM documentos_cargados
             WHERE solicitud_id = %s AND requerido_id = %s
            RETURNING ruta_relativa
            """,
            (str(solicitud_id), requerido_id),
        )
        fila = cursor.fetchone()
        conexion.commit()

    if fila is not None:
        archivo = ajustes.directorio_datos / fila["ruta_relativa"]
        if archivo.exists():
            archivo.unlink()
    return Response(status_code=204)


@router.post("/{solicitud_id}/radicar", response_model=ResultadoRadicacion)
def radicar(
    solicitud_id: UUID,
    tareas: BackgroundTasks,
    pool: Any = Depends(obtener_pool),
    ajustes: AjustesAPI = Depends(obtener_ajustes),
) -> ResultadoRadicacion:
    """Corre el A1 y persiste el expediente.

    Un pago que no cuadra NO es un error de esta API: el A1 corta en el paso 3,
    el expediente sale SUSPENDIDO_POR_INCONSISTENCIA y esto devuelve 200 con
    `suspendido: true`. Es un resultado legitimo del tramite.
    """
    try:
        resultado = radicar_solicitud(pool, ajustes, solicitud_id)
    except ErrorRadicacion as error:
        raise HTTPException(error.codigo, str(error)) from error

    # Un expediente suspendido no se reparte, asi que tampoco se audita: seria
    # gasto sin destino. Los demas disparan A2, A3 y A4 en segundo plano; la
    # respuesta al solicitante no espera por ellos.
    if not resultado["suspendido"]:
        radicado = resultado["radicado"]
        carpeta = ajustes.directorio_dossieres / radicado
        programar(pool.connection, radicado)
        tareas.add_task(
            ejecutar_agentes, pool.connection, ajustes, radicado, carpeta
        )
    return ResultadoRadicacion(**resultado)


# ------------------------------------------------------- evidencia por enlace


@router.get("/{solicitud_id}/enlaces", response_model=list[EnlaceEvidencia])
def leer_enlaces(
    solicitud_id: UUID, pool: Any = Depends(obtener_pool)
) -> list[EnlaceEvidencia]:
    with pool.connection() as conexion, conexion.cursor() as cursor:
        _leer(cursor, solicitud_id)
        return _enlaces(cursor, solicitud_id)


@router.post("/{solicitud_id}/enlaces", response_model=EnlaceEvidencia, status_code=201)
def agregar_enlace(
    solicitud_id: UUID, cuerpo: CrearEnlace, pool: Any = Depends(obtener_pool)
) -> EnlaceEvidencia:
    """Registra evidencia publicada como enlace, en vez de como archivo.

    Es opcional y no reemplaza ningun documento obligatorio: es un atajo para que
    el evaluador llegue a la fuente sin descargar y volver a subir lo que ya esta
    publicado. Aqui no se descarga el contenido; la verificacion la hace el
    agente contra la fuente publica.
    """
    try:
        tipo, titulo_sugerido, referencia = clasificar(cuerpo.url)
    except EnlaceInvalido as error:
        raise HTTPException(422, str(error)) from error

    with pool.connection() as conexion, conexion.cursor() as cursor:
        _exigir_borrador(cursor, solicitud_id)
        cursor.execute(
            """
            INSERT INTO enlaces_evidencia (solicitud_id, url, titulo, tipo, referencia)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (solicitud_id, url) DO UPDATE SET titulo = EXCLUDED.titulo
            RETURNING id, url, titulo, tipo, referencia, creado_en
            """,
            (
                str(solicitud_id),
                cuerpo.url.strip(),
                (cuerpo.titulo or titulo_sugerido).strip(),
                tipo,
                referencia,
            ),
        )
        fila = cursor.fetchone()
        conexion.commit()
    return EnlaceEvidencia(**fila)


@router.delete("/{solicitud_id}/enlaces/{enlace_id}", status_code=204)
def eliminar_enlace(
    solicitud_id: UUID, enlace_id: UUID, pool: Any = Depends(obtener_pool)
) -> None:
    with pool.connection() as conexion, conexion.cursor() as cursor:
        _exigir_borrador(cursor, solicitud_id)
        cursor.execute(
            "DELETE FROM enlaces_evidencia WHERE id = %s AND solicitud_id = %s",
            (enlace_id, str(solicitud_id)),
        )
        if cursor.rowcount == 0:
            raise HTTPException(404, "No existe ese enlace en la solicitud")
        conexion.commit()
