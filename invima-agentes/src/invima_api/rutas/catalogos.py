"""Catalogos que alimentan el wizard del solicitante."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ..esquemas import (
    Catalogos,
    ItemCatalogo,
    ItemDocumentoRequerido,
    ItemMetodoPago,
    ItemModuloCtd,
    ItemTarifa,
)
from .comun import obtener_pool

router = APIRouter(tags=["catalogos"])


@router.get("/catalogos", response_model=Catalogos)
def leer_catalogos(pool: Any = Depends(obtener_pool)) -> Catalogos:
    with pool.connection() as conexion, conexion.cursor() as cursor:
        cursor.execute(
            "SELECT id, etiqueta, descripcion FROM tipos_tramite "
            "WHERE activo ORDER BY orden, id"
        )
        tramites = [ItemCatalogo(**fila) for fila in cursor.fetchall()]

        cursor.execute(
            "SELECT id, etiqueta, descripcion FROM tipos_producto "
            "WHERE activo ORDER BY orden, id"
        )
        productos = [ItemCatalogo(**fila) for fila in cursor.fetchall()]

        cursor.execute("SELECT codigo, concepto, valor FROM tarifas ORDER BY codigo")
        tarifas = [ItemTarifa(**fila) for fila in cursor.fetchall()]

        cursor.execute("SELECT id, etiqueta FROM metodos_pago ORDER BY orden, id")
        metodos = [ItemMetodoPago(**fila) for fila in cursor.fetchall()]

        cursor.execute("SELECT id, titulo FROM modulos_ctd ORDER BY orden, id")
        modulos = list(cursor.fetchall())

        cursor.execute(
            "SELECT id, modulo_id, nombre, obligatorio, folio_destino "
            "FROM documentos_requeridos ORDER BY modulo_id, orden, id"
        )
        documentos = list(cursor.fetchall())

    por_modulo: dict[str, list[ItemDocumentoRequerido]] = {}
    for documento in documentos:
        por_modulo.setdefault(documento["modulo_id"], []).append(
            ItemDocumentoRequerido(
                id=documento["id"],
                nombre=documento["nombre"],
                obligatorio=documento["obligatorio"],
                folio_destino=documento["folio_destino"],
            )
        )

    return Catalogos(
        tipos_tramite=tramites,
        tipos_producto=productos,
        tarifas=tarifas,
        metodos_pago=metodos,
        modulos_ctd=[
            ItemModuloCtd(
                id=modulo["id"],
                titulo=modulo["titulo"],
                documentos=por_modulo.get(modulo["id"], []),
            )
            for modulo in modulos
        ],
    )
