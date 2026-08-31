"""Radicacion: arma la carpeta del dossier, corre el A1 y persiste todo.

El A1 no sabe que existe un wizard. Lo unico que entiende es una carpeta con
folios en Markdown, asi que este servicio traduce la solicitud a esa forma:
copia cada documento cargado al nombre de folio que el parser espera y, cuando
el solicitante no cargo el formulario, lo sintetiza con lo que declaro.

Orden de las transacciones, que importa:

  1. Tx corta: se bloquea la solicitud, se calcula el radicado y se RESERVA la
     fila del expediente. Se hace commit antes de correr el agente, porque el
     agente escribe la misma fila desde otra conexion del pool y se quedaria
     esperando un lock nuestro.
  2. Fuera de transaccion: se arma la carpeta y corre el A1, que persiste el
     expediente y su bitacora con sus propios adaptadores Postgres.
  3. Tx final: la solicitud queda RADICADA, se pueblan fuentes y checklist.
"""

from __future__ import annotations

import hashlib
import re
import shutil
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from invima_a1.aplicacion.procesar_radicacion import ProcesarRadicacionUseCase
from invima_a1.config import Ajustes
from invima_a1.config_postgres import construir_dependencias_postgres

from ..config import AjustesAPI
from .enlaces import folio_de_enlaces
from .fuentes import extraer_fuentes

#: Primer consecutivo. El contrato muestra 2026SM-014832 como ejemplo vivo.
BASE_CONSECUTIVO = 14832
PREFIJO_RADICADO = "2026SM-"
_RE_RADICADO = re.compile(rf"^{re.escape(PREFIJO_RADICADO)}(\d+)$")

#: Folio que alimenta los pasos 2 a 8 del agente.
FOLIO_FORMULARIO = "modulo1_fm113"

#: Lo que el solicitante escribio en el sistema, como folio aparte.
#: No es lo mismo que el formulario radicado: la diferencia entre ambos es
#: justamente lo que hay que mostrarle al evaluador. Antes se escribia solo
#: cuando faltaba el formulario, de modo que al subir el PDF real esta fuente
#: desaparecia y el agente perdia los campos que el formato oficial no desglosa
#: (principio activo, concentracion y forma farmaceutica van en una sola linea).
FOLIO_DECLARADO = "modulo1_declarado"

#: Evidencia aportada como enlace publico. Se escribe como folio del Modulo 1
#: para que el agente la lea igual que cualquier otro: los identificadores NCT
#: que traiga el enlace los verifica solo contra ClinicalTrials.gov.
FOLIO_ENLACES = "modulo1_enlaces"

#: Extensiones cuyo contenido el parser sabe leer como texto.
EXTENSIONES_DE_TEXTO = frozenset({".md", ".txt"})

#: Minimo de caracteres para dar por buena la extraccion de un PDF. Por debajo
#: de esto casi siempre es un escaneo sin capa de texto: se archiva como adjunto
#: en vez de alimentar al agente con una pagina en blanco.
MINIMO_TEXTO_PDF = 200


class ErrorRadicacion(Exception):
    """Falla de negocio en la radicacion. `codigo` es el status HTTP a devolver."""

    def __init__(self, mensaje: str, codigo: int = 409) -> None:
        super().__init__(mensaje)
        self.codigo = codigo


# --------------------------------------------------------------- funciones puras


def siguiente_radicado(ultimo: str | None) -> str:
    """Consecutivo, no aleatorio: el numero de radicado es un orden de llegada.

    Sin expedientes previos arranca en BASE_CONSECUTIVO.
    """
    if not ultimo:
        return f"{PREFIJO_RADICADO}{BASE_CONSECUTIVO:06d}"
    coincidencia = _RE_RADICADO.match(ultimo.strip())
    if not coincidencia:
        return f"{PREFIJO_RADICADO}{BASE_CONSECUTIVO:06d}"
    return f"{PREFIJO_RADICADO}{int(coincidencia.group(1)) + 1:06d}"


def sha256_de(contenido: bytes) -> str:
    return hashlib.sha256(contenido).hexdigest()


def formatear_pesos(valor: Decimal | float | int | None) -> str:
    """Formato colombiano: punto de miles, coma decimal. '14.850.000,00'."""
    if valor is None:
        return "No suministrado"
    return f"{Decimal(str(valor)):,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")


def _campo(datos: dict[str, Any], *claves: str) -> str | None:
    """Lee el primer alias presente. El wizard puede mandar camelCase o snake_case."""
    for clave in claves:
        for variante in (clave, _a_snake(clave)):
            if variante in datos:
                valor = datos[variante]
                if valor is None:
                    continue
                texto = str(valor).strip()
                if texto:
                    return texto
    return None


def _a_snake(texto: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", texto).lower()


def _o(valor: str | None) -> str:
    return valor if valor else "No suministrado"


def sintetizar_fm113(
    datos_declarados: dict[str, Any],
    comprobante: str | None,
    codigo_tarifa: str | None,
    valor_pagado: Decimal | None,
    tipo_tramite_etiqueta: str = "Registro Sanitario de Molecula",
    ruta_estudio_defecto: str = "Evaluacion farmacologica previa",
) -> str:
    """Reconstruye el folio ASS-RSA-FM113 con lo que el solicitante declaro.

    ORIGEN DECLARATIVO: este folio no lo aporto el solicitante como documento,
    lo escribe el sistema con los datos que el mismo tecleo en los pasos 2 y 4
    del wizard, mas los datos de pago de la solicitud. Para el agente es
    contenido EXTRAIDO de un folio del expediente, y eso es correcto: es la
    declaracion del solicitante. Lo que NO es, es un documento aportado ni una
    verificacion; el evaluador ve la diferencia comparando este folio contra
    `solicitudes.datos_declarados`, que queda intacto en la base.

    El formato replica seccion por seccion (y marca de pagina por marca de
    pagina) el fixture data/fixtures/dossier_corazilimab/modulo1_fm113.md,
    porque es lo que el parser y el extractor determinista saben leer.
    """
    declarados = datos_declarados or {}
    certificado = declarados.get("certificado") or declarados.get("certificado_internacional") or {}
    if not isinstance(certificado, dict):
        certificado = {}

    aprobaciones = declarados.get("aprobaciones") or declarados.get("aprobaciones_declaradas") or []
    if not isinstance(aprobaciones, list):
        aprobaciones = []

    nct_ids = declarados.get("nctIds") or declarados.get("nct_ids") or []
    if not isinstance(nct_ids, list):
        nct_ids = []

    check = declarados.get("moleculaNoIncluidaNormas")
    if check is None:
        check = declarados.get("molecula_no_incluida_normas")
    check_texto = "SI" if bool(check) else "NO"

    lineas: list[str] = [
        "<!-- pagina: 1 -->",
        "# INSTITUTO NACIONAL DE VIGILANCIA DE MEDICAMENTOS Y ALIMENTOS",
        "# Formato ASS-RSA-FM113 - Solicitud de Registro Sanitario",
        "",
        "> FOLIO SINTETIZADO POR EL SISTEMA A PARTIR DE LOS DATOS DECLARADOS POR EL",
        "> SOLICITANTE EN EL FORMULARIO WEB. No es un documento aportado al expediente.",
        "",
        "## Seccion 1. Datos del Solicitante",
        "",
        f"Razon Social del Titular: {_o(_campo(declarados, 'razonSocialTitular', 'nombreTitular', 'titular'))}",
        f"Representante en Colombia: {_o(_campo(declarados, 'representanteColombia', 'representante'))}",
        f"NIT: {_o(_campo(declarados, 'nit', 'nitRepresentante'))}",
        "",
        "<!-- pagina: 2 -->",
        "## Seccion 2. Datos del Producto",
        "",
        f"Nombre del Producto: {_o(_campo(declarados, 'nombre', 'nombreProducto'))}",
        f"Principio Activo: {_o(_campo(declarados, 'principioActivo'))}",
        f"Concentracion: {_o(_campo(declarados, 'concentracion'))}",
        f"Forma Farmaceutica: {_o(_campo(declarados, 'formaFarmaceutica'))}",
        f"Indicacion Solicitada: {_o(_campo(declarados, 'indicacionSolicitada'))}",
        "",
        "## Seccion 3. Datos del Tramite",
        "",
        f"Tipo de Tramite: {_campo(declarados, 'tipoTramiteTexto') or tipo_tramite_etiqueta}",
        f"Modalidad: {_o(_campo(declarados, 'modalidad'))}",
        f"Ruta de Estudio: {_campo(declarados, 'rutaEstudio') or ruta_estudio_defecto}",
        "",
        "<!-- pagina: 3 -->",
        "## Seccion 4. Datos de Pago",
        "",
        f"Comprobante No: {_o(comprobante)}",
        f"Codigo de Tarifa: {_o(codigo_tarifa)}",
        f"Valor Pagado: {formatear_pesos(valor_pagado)}",
        "",
        "## Seccion 5. Observaciones del Solicitante",
        "",
        f"Observaciones: {_campo(declarados, 'observaciones') or 'Ninguna'}",
        "",
        "<!-- pagina: 4 -->",
        "## Seccion 6. Autovalidacion Farmaceutica",
        "",
        f"Molecula NO Incluida en Normas Farmacologicas: {check_texto}",
        "",
        "## Seccion 7. Documentos de Validacion Internacional",
        "",
        f"Tipo de Certificado: {_o(_campo(certificado, 'tipo', 'tipoCertificado'))}",
        f"Numero de Certificado: {_o(_campo(certificado, 'numero', 'numeroCertificado'))}",
        f"Pais Emisor: {_o(_campo(certificado, 'paisEmisor'))}",
        f"Autoridad Emisora: {_o(_campo(certificado, 'autoridadEmisora'))}",
        "",
        "### Matriz de Aprobaciones Internacionales",
        "",
        "| Agencia | Fecha de Aprobacion | Indicacion Aprobada |",
        "| --- | --- | --- |",
    ]

    for aprobacion in aprobaciones:
        if not isinstance(aprobacion, dict):
            continue
        agencia = _campo(aprobacion, "agencia")
        if not agencia:
            continue
        lineas.append(
            f"| {agencia.upper()} "
            f"| {_o(_campo(aprobacion, 'fechaAprobacion', 'fecha'))} "
            f"| {_o(_campo(aprobacion, 'indicacionAprobada', 'indicacion'))} |"
        )

    identificadores = ", ".join(str(n).strip() for n in nct_ids if str(n).strip())
    lineas += [
        "",
        "### Estudios Clinicos Registrados",
        "",
        f"Identificadores NCT declarados: {identificadores or 'No suministrado'}",
        "",
    ]
    return "\n".join(lineas)


def extraer_texto_pdf(ruta: Path) -> str | None:
    """Saca la capa de texto de un PDF. Devuelve None si no la tiene.

    Se usa pypdf y no un OCR pesado porque los folios del dossier son PDF
    generados, no escaneos. Cuando llegue un escaneo real esta funcion devuelve
    None y el folio se archiva como adjunto: es preferible a alimentar al agente
    con paginas vacias y que concluya que faltan datos que si estaban.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        return None

    try:
        lector = PdfReader(str(ruta))
        partes: list[str] = []
        for numero, pagina in enumerate(lector.pages, start=1):
            texto = (pagina.extract_text() or "").strip()
            if texto:
                partes.append(f"<!-- pagina: {numero} -->\n{texto}")
    except Exception:  # noqa: BLE001 - un PDF ilegible no debe tumbar la radicacion
        return None

    if not partes:
        return None
    completo = "\n\n".join(partes)
    return completo if len(completo) >= MINIMO_TEXTO_PDF else None


def destino_de_folio(folio_destino: str | None, nombre_archivo: str) -> tuple[str, bool]:
    """Decide donde va un documento cargado dentro de la carpeta del dossier.

    Devuelve (ruta relativa a la carpeta, alimenta_al_parser).

    El parser hace glob en la RAIZ de la carpeta, asi que todo lo que no deba
    alimentarlo va a la subcarpeta `adjuntos/`: se archiva y se puede auditar,
    pero no entra al agente.

    Un PDF con folio asignado SI alimenta: se le extrae la capa de texto a un
    sidecar Markdown y el binario original se conserva en `adjuntos/`, de modo
    que el evaluador pueda abrir el folio tal como se radico.
    """
    extension = Path(nombre_archivo).suffix.lower()
    if folio_destino and extension in EXTENSIONES_DE_TEXTO:
        return f"{folio_destino}.md", True
    return f"adjuntos/{nombre_archivo}", False


def armar_carpeta_dossier(
    carpeta: Path,
    documentos: list[dict[str, Any]],
    raiz_cargas: Path,
) -> set[str]:
    """Copia los documentos cargados a la carpeta del dossier.

    Devuelve el conjunto de folios que quedaron alimentando al parser.
    """
    if carpeta.exists():
        shutil.rmtree(carpeta)
    carpeta.mkdir(parents=True)

    folios: set[str] = set()
    for documento in documentos:
        nombre = documento["nombre_archivo"]
        folio_destino = documento.get("folio_destino")
        relativo, alimenta = destino_de_folio(folio_destino, nombre)
        destino = carpeta / relativo
        destino.parent.mkdir(parents=True, exist_ok=True)
        origen = raiz_cargas / documento["ruta_relativa"]
        if not origen.exists():
            raise ErrorRadicacion(
                f"El archivo cargado para {documento['requerido_id']} ya no esta "
                f"en disco: {documento['ruta_relativa']}",
                codigo=409,
            )
        shutil.copyfile(origen, destino)
        if alimenta:
            folios.add(Path(relativo).stem)
            continue

        # PDF con folio asignado: el binario ya quedo archivado; ahora se le
        # extrae el texto para que el agente pueda leer el folio de verdad.
        if folio_destino and Path(nombre).suffix.lower() == ".pdf":
            texto = extraer_texto_pdf(destino)
            if texto:
                (carpeta / f"{folio_destino}.md").write_text(
                    f"<!-- folio: {folio_destino} | origen: {nombre} -->\n\n{texto}",
                    encoding="utf-8",
                )
                folios.add(folio_destino)
    return folios


# ------------------------------------------------------------------ persistencia


_COLUMNAS_SOLICITUD = (
    "id, solicitante_id, estado, tipo_tramite, tipo_producto, datos_declarados, "
    "tarifa_codigo, metodo_pago, comprobante, valor_pagado, fecha_pago, radicado"
)


def _cargar_solicitud_bloqueada(cursor: Any, solicitud_id: UUID) -> dict[str, Any]:
    cursor.execute(
        f"SELECT {_COLUMNAS_SOLICITUD} FROM solicitudes WHERE id = %s FOR UPDATE",
        (str(solicitud_id),),
    )
    fila = cursor.fetchone()
    if fila is None:
        raise ErrorRadicacion(f"No existe la solicitud {solicitud_id}", codigo=404)
    return fila


def _documentos_de(cursor: Any, solicitud_id: UUID) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT d.requerido_id, d.nombre_archivo, d.ruta_relativa, r.folio_destino
          FROM documentos_cargados d
          JOIN documentos_requeridos r ON r.id = d.requerido_id
         WHERE d.solicitud_id = %s
         ORDER BY r.modulo_id, r.orden
        """,
        (str(solicitud_id),),
    )
    return list(cursor.fetchall())


def _etiqueta(cursor: Any, tabla: str, identificador: str | None, defecto: str) -> str:
    if not identificador:
        return defecto
    cursor.execute(f"SELECT etiqueta FROM {tabla} WHERE id = %s", (identificador,))
    fila = cursor.fetchone()
    return fila["etiqueta"] if fila else defecto


def _verificar_completitud(solicitud: dict[str, Any]) -> None:
    if solicitud["estado"] != "BORRADOR":
        raise ErrorRadicacion(
            f"La solicitud ya no esta en BORRADOR (estado actual: {solicitud['estado']})",
            codigo=409,
        )
    faltantes = [
        etiqueta
        for campo, etiqueta in (
            ("tipo_tramite", "tipo de tramite"),
            ("tipo_producto", "tipo de producto"),
            ("tarifa_codigo", "codigo de tarifa"),
            ("comprobante", "numero de comprobante"),
            ("valor_pagado", "valor pagado"),
        )
        if not solicitud.get(campo)
    ]
    if faltantes:
        raise ErrorRadicacion(
            "La solicitud esta incompleta. Falta: " + ", ".join(faltantes),
            codigo=422,
        )


def _reservar_radicado(cursor: Any, solicitud_id: UUID, carpeta_base: Path) -> str:
    cursor.execute(
        """
        SELECT radicado FROM expedientes
         WHERE radicado LIKE %s
         ORDER BY radicado DESC
         LIMIT 1
        """,
        (PREFIJO_RADICADO + "%",),
    )
    fila = cursor.fetchone()
    radicado = siguiente_radicado(fila["radicado"] if fila else None)
    cursor.execute(
        """
        INSERT INTO expedientes
            (radicado, solicitud_id, fecha_radicacion, estado, carpeta_dossier)
        VALUES (%s, %s, %s, 'RECIBIDO', %s)
        """,
        (radicado, str(solicitud_id), date.today(), str(carpeta_base / radicado)),
    )
    return radicado


def _poblar_evaluacion(cursor: Any, radicado: str, payload: dict[str, Any]) -> None:
    for fuente in extraer_fuentes(payload):
        cursor.execute(
            """
            INSERT INTO fuentes_externas
                (radicado, fuente, titulo, tipo, pais, fecha, url, encontrada,
                 observaciones)
            VALUES (%(radicado)s, %(fuente)s, %(titulo)s, %(tipo)s, %(pais)s,
                    %(fecha)s, %(url)s, %(encontrada)s, %(observaciones)s)
            ON CONFLICT (radicado, fuente, titulo) DO NOTHING
            """,
            {"radicado": radicado, **fuente},
        )

    # El checklist se COPIA de la plantilla, no se referencia: el evaluador
    # ajusta el texto de sus criterios y eso no debe reescribir la plantilla.
    cursor.execute(
        """
        INSERT INTO checklist_items (radicado, texto, origen, orden)
        SELECT %s, texto, 'PLANTILLA', orden FROM checklist_plantilla ORDER BY orden
        """,
        (radicado,),
    )


def radicar_solicitud(
    pool: Any, ajustes: AjustesAPI, solicitud_id: UUID
) -> dict[str, Any]:
    """Ejecuta la radicacion completa y devuelve el ResultadoRadicacion."""
    with pool.connection() as conexion:
        with conexion.cursor() as cursor:
            solicitud = _cargar_solicitud_bloqueada(cursor, solicitud_id)
            _verificar_completitud(solicitud)
            documentos = _documentos_de(cursor, solicitud_id)
            etiqueta_tramite = _etiqueta(
                cursor, "tipos_tramite", solicitud["tipo_tramite"], "Registro nuevo"
            )
            etiqueta_producto = _etiqueta(
                cursor, "tipos_producto", solicitud["tipo_producto"], "No declarado"
            )
            radicado = _reservar_radicado(
                cursor, solicitud_id, ajustes.directorio_dossieres
            )
        conexion.commit()

    carpeta = ajustes.directorio_dossieres / radicado
    try:
        folios = armar_carpeta_dossier(carpeta, documentos, ajustes.directorio_datos)

        # Siempre: es una fuente propia, no un relleno cuando falta el formulario.
        (carpeta / f"{FOLIO_DECLARADO}.md").write_text(
            sintetizar_fm113(
                datos_declarados=solicitud["datos_declarados"] or {},
                comprobante=solicitud["comprobante"],
                codigo_tarifa=solicitud["tarifa_codigo"],
                valor_pagado=solicitud["valor_pagado"],
                tipo_tramite_etiqueta=etiqueta_tramite,
            ),
            encoding="utf-8",
        )

        cursor_enlaces = None
        with pool.connection() as conexion, conexion.cursor() as cur:
            cur.execute(
                "SELECT url, tipo, referencia FROM enlaces_evidencia "
                "WHERE solicitud_id = %s ORDER BY creado_en",
                (str(solicitud_id),),
            )
            cursor_enlaces = [dict(f) for f in cur.fetchall()]
        if cursor_enlaces:
            (carpeta / f"{FOLIO_ENLACES}.md").write_text(
                folio_de_enlaces(cursor_enlaces), encoding="utf-8"
            )

        dependencias = construir_dependencias_postgres(
            replace(
                Ajustes.desde_entorno(offline=ajustes.offline),
                directorio_datos=ajustes.directorio_datos,
            ),
            conexiones=pool.connection,
            solicitud_id=solicitud_id,
            carpeta_dossier=carpeta,
        )
        resultado = ProcesarRadicacionUseCase(dependencias).ejecutar(
            carpeta, radicado, patron_folios="modulo1_*"
        )
    except Exception:
        # La reserva del radicado ya esta comprometida; si el agente no llego a
        # producir un expediente, se libera el numero en vez de dejar una fila
        # huerfana en estado RECIBIDO.
        with pool.connection() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM expedientes WHERE radicado = %s AND estado = 'RECIBIDO'",
                    (radicado,),
                )
            conexion.commit()
        raise

    payload = resultado.payload
    with pool.connection() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                UPDATE solicitudes
                   SET estado = 'RADICADA', radicado = %s, radicada_en = now(),
                       actualizada_en = now()
                 WHERE id = %s
                """,
                (radicado, str(solicitud_id)),
            )
            _poblar_evaluacion(cursor, radicado, payload)
        conexion.commit()

    pago = (payload.get("radicacion") or {}).get("pago") or {}
    return {
        "radicado": radicado,
        "fecha_radicacion": payload["radicacion"]["fecha_radicacion"],
        "estado": payload["radicacion"]["estado"],
        "suspendido": resultado.suspendido,
        "tipo_tramite": etiqueta_tramite,
        "tipo_producto": etiqueta_producto,
        "validacion_pago": {
            "verificado": bool(pago.get("verificado")),
            "resultado": str(pago.get("resultado_validacion", "")),
            "inconsistencias": list(pago.get("inconsistencias") or []),
        },
        "advertencia": payload["supervision_humana"]["advertencia"],
    }


__all__ = [
    "BASE_CONSECUTIVO",
    "ErrorRadicacion",
    "armar_carpeta_dossier",
    "destino_de_folio",
    "formatear_pesos",
    "radicar_solicitud",
    "sha256_de",
    "siguiente_radicado",
    "sintetizar_fm113",
]
