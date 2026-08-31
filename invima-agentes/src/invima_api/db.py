"""Pool de conexiones y aplicacion de migraciones al arrancar.

Sobre la espera del arranque: el contenedor oficial de PostgreSQL levanta un
servidor temporal durante initdb, y `pg_isready` responde OK contra ESE servidor
antes de que la base definitiva exista. Por eso aqui no se usa pg_isready ni un
sleep fijo: se reintenta la conexion Y una consulta real hasta que responda.

Un fallo de conexion dentro del bucle de espera es reintento. Un fallo de SQL
dentro de una migracion es fatal y se propaga con su mensaje completo: una
migracion a medias es peor que no arrancar.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

registro = logging.getLogger("invima_api.db")

INTENTOS_MAXIMOS = 60
ESPERA_INICIAL = 0.25
ESPERA_MAXIMA = 2.0


def esperar_base(dsn: str, intentos: int = INTENTOS_MAXIMOS) -> None:
    """Bloquea hasta que la base responda una consulta real, o se rinde.

    No basta con abrir el socket: se ejecuta `SELECT 1` porque durante initdb hay
    un servidor que acepta conexiones y todavia no tiene la base definitiva.
    """
    espera = ESPERA_INICIAL
    ultimo: Exception | None = None
    for intento in range(1, intentos + 1):
        try:
            with psycopg.connect(dsn, connect_timeout=3) as conexion:
                with conexion.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
            registro.info("Base disponible en el intento %d", intento)
            return
        except psycopg.Error as error:
            ultimo = error
            time.sleep(espera)
            espera = min(espera * 1.5, ESPERA_MAXIMA)
    raise RuntimeError(
        f"La base no respondio tras {intentos} intentos. Ultimo error: {ultimo}"
    )


def archivos_de_migracion(carpeta: Path) -> list[Path]:
    """Los .sql en orden lexicografico: 01, 02, 03, 04."""
    return sorted(carpeta.glob("*.sql"))


def aplicar_migraciones(dsn: str, carpeta: Path) -> list[str]:
    """Aplica los .sql en orden. Son idempotentes por diseno: no hay tabla de
    control de migraciones y no hace falta.

    Cada archivo trae su propio BEGIN/COMMIT, asi que la conexion va en
    autocommit para que esas marcas signifiquen lo que dicen.
    """
    archivos = archivos_de_migracion(carpeta)
    if not archivos:
        raise RuntimeError(f"No hay archivos .sql en {carpeta}")

    aplicados: list[str] = []
    with psycopg.connect(dsn, autocommit=True) as conexion:
        for archivo in archivos:
            sql = archivo.read_text(encoding="utf-8")
            try:
                with conexion.cursor() as cursor:
                    cursor.execute(sql)
            except psycopg.Error as error:
                raise RuntimeError(
                    f"Fallo la migracion {archivo.name}: {error}"
                ) from error
            registro.info("Migracion aplicada: %s", archivo.name)
            aplicados.append(archivo.name)
    return aplicados


def abrir_pool(dsn: str) -> ConnectionPool:
    pool = ConnectionPool(
        dsn,
        min_size=1,
        max_size=10,
        kwargs={"row_factory": dict_row},
        open=True,
    )
    pool.wait(timeout=30)
    return pool


__all__ = [
    "abrir_pool",
    "aplicar_migraciones",
    "archivos_de_migracion",
    "esperar_base",
]
