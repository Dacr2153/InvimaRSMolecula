"""Precarga del borrador de demostracion.

Para que una demo sea "siguiente, siguiente, radicar" hace falta que el borrador
nazca completo. Los datos NO son inventados: salen del Modulo 1 del dossier de
Corazilimab que el INVIMA entrego como insumo del evento, y los folios son los
PDF de ese mismo dossier repartidos en sus documentos requeridos.

Se activa con INVIMA_DEMO=1 (por defecto). Apagarlo devuelve el borrador vacio,
que es el comportamiento correcto fuera de una demostracion.
"""

from __future__ import annotations

import logging
import mimetypes
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

registro = logging.getLogger("invima_api.demo")

#: Transcrito del formato ASS-RSA-FM113 del dossier oficial (Modulo 1, folios 1-4).
DATOS_DECLARADOS: dict[str, str] = {
    "nombre": "CORAZILIMAB 150 mg/mL SOLUCIÓN INYECTABLE EN JERINGA PRECARGADA",
    "principioActivo": "Corazilimab",
    "concentracion": "150 mg/mL",
    "formaFarmaceutica": "Solución inyectable en jeringa precargada",
    "titular": "BIOTEC GLOBAL THERAPEUTICS LTD.",
    "solicitante": "BIOFARMA ANDINA S.A.S.",
    "fabricante": "CellGenix Biologics Facility B (Martinsried, Alemania)",
    "fabricanteProductoTerminado": "PharmaFill Solutions Inc. (Groningen, Países Bajos)",
    "acondicionador": "Biologística Colombia S.A.S. (Cota, Colombia)",
    "importador": "BIOFARMA ANDINA S.A.S.",
    "nit": "901.458.789-2",
    "paisOrigen": "Reino Unido",
    "viaAdministracion": "Subcutánea",
    "indicacion": (
        "Hipertensión arterial pulmonar en adultos y adolescentes mayores de 12 años"
    ),
    "codigoDesarrollo": "CRZ-042",
    "correo": "regulatorio@biofarma-andina.com",
    "telefono": "57 601 745 2180",
    "direccion": "Carrera 15 No. 93-60, Oficina 702, Bogotá D.C.",
    "observaciones": (
        "Medicamento biológico de nueva molécula. Código de desarrollo consignado "
        "en M2: CRZ-042. Solicitud inicial para Colombia."
    ),
}

TIPO_TRAMITE = "registro-nuevo"
TIPO_PRODUCTO = "biologico"
TARIFA_CODIGO = "1004"
METODO_PAGO = "pse"
COMPROBANTE = "BAN-8839201"
VALOR_PAGADO = Decimal("14850000.00")
FECHA_PAGO = "2026-08-20"


def _primer_id(cursor: Any, tabla: str, preferido: str) -> str | None:
    """El id preferido si existe en el catalogo; si no, el primero.

    Los ids del catalogo los siembra la migracion y podrian cambiar; la demo no
    debe romperse por eso.
    """
    cursor.execute("SELECT id FROM %s WHERE id = %%s" % tabla, (preferido,))
    if cursor.fetchone():
        return preferido
    cursor.execute("SELECT id FROM %s ORDER BY orden, id LIMIT 1" % tabla)
    fila = cursor.fetchone()
    return fila["id"] if fila else None


def sembrar_borrador(
    cursor: Any,
    solicitud_id: UUID,
    directorio_demo: Path,
    directorio_datos: Path,
    sha256_de: Any,
) -> int:
    """Deja el borrador listo para radicar. Devuelve cuantos folios adjunto.

    Solo adjunta el folio cuyo archivo existe en `directorio_demo` con el nombre
    del documento requerido. Si falta uno, ese documento simplemente queda sin
    cargar y la interfaz lo pedira: es preferible a fabricar un folio vacio.
    """
    tramite = _primer_id(cursor, "tipos_tramite", TIPO_TRAMITE)
    producto = _primer_id(cursor, "tipos_producto", TIPO_PRODUCTO)

    cursor.execute("SELECT codigo FROM tarifas WHERE codigo = %s", (TARIFA_CODIGO,))
    tarifa = TARIFA_CODIGO if cursor.fetchone() else None
    cursor.execute("SELECT id FROM metodos_pago WHERE id = %s", (METODO_PAGO,))
    metodo = METODO_PAGO if cursor.fetchone() else None
    if metodo is None:
        cursor.execute("SELECT id FROM metodos_pago ORDER BY id LIMIT 1")
        fila = cursor.fetchone()
        metodo = fila["id"] if fila else None

    import json

    cursor.execute(
        """
        UPDATE solicitudes
           SET tipo_tramite = %s, tipo_producto = %s,
               datos_declarados = %s::jsonb,
               tarifa_codigo = %s, metodo_pago = %s, comprobante = %s,
               valor_pagado = %s, fecha_pago = %s,
               actualizada_en = now()
         WHERE id = %s
        """,
        (
            tramite,
            producto,
            json.dumps(DATOS_DECLARADOS, ensure_ascii=False),
            tarifa,
            metodo,
            COMPROBANTE,
            VALOR_PAGADO,
            FECHA_PAGO,
            str(solicitud_id),
        ),
    )

    if not directorio_demo.is_dir():
        registro.warning("No hay carpeta de folios de demo en %s", directorio_demo)
        return 0

    cursor.execute("SELECT id FROM documentos_requeridos ORDER BY orden, id")
    requeridos = [f["id"] for f in cursor.fetchall()]

    adjuntados = 0
    for requerido_id in requeridos:
        origen = next(
            (
                c
                for c in (directorio_demo / f"{requerido_id}{ext}" for ext in (".pdf", ".md", ".txt"))
                if c.is_file()
            ),
            None,
        )
        if origen is None:
            continue

        contenido = origen.read_bytes()
        relativo = Path("cargas") / str(solicitud_id) / origen.name
        destino = directorio_datos / relativo
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(contenido)

        cursor.execute(
            """
            INSERT INTO documentos_cargados
                (solicitud_id, requerido_id, nombre_archivo, ruta_relativa,
                 tamano_bytes, tipo_mime, sha256)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (solicitud_id, requerido_id) DO NOTHING
            """,
            (
                str(solicitud_id),
                requerido_id,
                origen.name,
                str(relativo),
                len(contenido),
                mimetypes.guess_type(origen.name)[0] or "application/octet-stream",
                sha256_de(contenido),
            ),
        )
        adjuntados += 1

    registro.info("Borrador de demo sembrado con %d folios", adjuntados)
    return adjuntados


__all__ = ["DATOS_DECLARADOS", "sembrar_borrador"]
