"""Piezas compartidas por los routers: acceso al pool y etiquetas de estado."""

from __future__ import annotations

from typing import Any

from fastapi import Request

from ..config import AjustesAPI

#: Etiquetas legibles de la maquina de estados del dominio. La API traduce; la
#: UI no reimplementa la maquina de estados ni inventa nombres.
ETIQUETAS_ESTADO = {
    "RECIBIDO": "Recibido",
    "INGESTADO": "Ingestado",
    "METADATOS_EXTRAIDOS": "Metadatos extraídos",
    "PAGO_VALIDADO": "Pago validado",
    "RELIANCE_COMPLETADO": "Reliance completado",
    "NORMAS_EVALUADAS": "Normas evaluadas",
    "RUTA_RECOMENDADA": "Ruta recomendada",
    "PENDIENTE_VALIDACION_HUMANA": "Pendiente de validación",
    "ENRUTADO": "Enrutado",
    "SUSPENDIDO_POR_INCONSISTENCIA": "Suspendido por inconsistencia",
    "DEVUELTO_POR_EVALUADOR": "Devuelto por el evaluador",
}

#: Estados desde los que la maquina de estados admite una decision humana.
ESTADOS_DECIDIBLES = frozenset(
    {"PENDIENTE_VALIDACION_HUMANA", "SUSPENDIDO_POR_INCONSISTENCIA"}
)


def etiqueta_estado(estado: str) -> str:
    return ETIQUETAS_ESTADO.get(estado, estado)


def obtener_pool(peticion: Request) -> Any:
    return peticion.app.state.pool


def obtener_ajustes(peticion: Request) -> AjustesAPI:
    return peticion.app.state.ajustes


__all__ = [
    "ESTADOS_DECIDIBLES",
    "ETIQUETAS_ESTADO",
    "etiqueta_estado",
    "obtener_ajustes",
    "obtener_pool",
]
