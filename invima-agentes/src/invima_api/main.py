"""Entrypoint de la API.

Arranque en tres tiempos, y el orden importa: esperar a que la base responda una
consulta real, aplicar las migraciones, y solo entonces abrir el pool. Si algo
de eso falla, el proceso no arranca: una API en pie contra un esquema a medias
produce errores que parecen de negocio y no lo son.

Todo cuelga de /api porque nginx sirve el frontend en la raiz y proxifica /api.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import AjustesAPI
from .db import abrir_pool, aplicar_migraciones, esperar_base
from .rutas import catalogos, expedientes, solicitudes

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
registro = logging.getLogger("invima_api")


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI) -> AsyncIterator[None]:
    ajustes = AjustesAPI.desde_entorno()
    app.state.ajustes = ajustes

    ajustes.directorio_dossieres.mkdir(parents=True, exist_ok=True)
    ajustes.directorio_cargas.mkdir(parents=True, exist_ok=True)

    registro.info("Esperando a la base de datos")
    esperar_base(ajustes.dsn)

    aplicados = aplicar_migraciones(ajustes.dsn, ajustes.directorio_migraciones)
    registro.info("Migraciones aplicadas: %s", ", ".join(aplicados))

    app.state.pool = abrir_pool(ajustes.dsn)
    registro.info(
        "API lista. Modo %s", "offline" if ajustes.offline else "en linea (consume credito)"
    )
    try:
        yield
    finally:
        app.state.pool.close()


def crear_app() -> FastAPI:
    app = FastAPI(
        title="INVIMA - Registro Sanitario de Molecula",
        version="0.1.0",
        summary="Radicacion y evaluacion asistida de expedientes CTD",
        description=(
            "Los agentes de esta plataforma apoyan la evaluacion; no la sustituyen. "
            "Ningun endpoint emite concepto tecnico ni decision administrativa: el "
            "unico que cambia el estado de un expediente es "
            "POST /api/expedientes/{radicado}/decision, y exige el nombre del "
            "servidor publico responsable (art. 7.1, Resolucion 2026025611)."
        ),
        lifespan=ciclo_de_vida,
    )

    ajustes = AjustesAPI.desde_entorno()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(ajustes.origenes_cors),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api = APIRouter(prefix="/api")
    api.include_router(catalogos.router)
    api.include_router(solicitudes.router)
    api.include_router(expedientes.router)
    app.include_router(api)

    @app.get("/api/salud", tags=["operacion"])
    def salud() -> dict[str, object]:
        """Sonda de vida. Toca la base: sin ella la API no sirve para nada."""
        with app.state.pool.connection() as conexion, conexion.cursor() as cursor:
            cursor.execute("SELECT count(*) AS n FROM expedientes")
            expedientes_en_base = cursor.fetchone()["n"]
        return {
            "estado": "ok",
            "offline": app.state.ajustes.offline,
            "expedientes": expedientes_en_base,
        }

    return app


app = crear_app()
