"""Consulta a la FDA por la API publica de openFDA.

Sin autenticacion y sin costo. Se consulta el endpoint de etiquetado
(`drug/label`) porque es el que trae la indicacion aprobada en texto, que es lo
que necesita el contraste. La URL consultada se devuelve para que quede citada.

Dos lecciones de las llamadas reales que obligaron a no quedarse con el primer
resultado:

1. Una busqueda por `metformin` devuelve como primer registro la etiqueta de
   SITAGLIPTINA + METFORMINA. Contrastar el dossier contra la etiqueta de un
   producto combinado seria un error de fondo, no de forma.
2. Varias moleculas tienen registros sin `indications_and_usage` mezclados con
   registros que si la traen. Para bosentan, el primero venia vacio y el
   segundo completo.

Por eso se piden varios registros y se elige por criterio explicito.
"""

from __future__ import annotations

import re
from typing import Any

import httpx

from ...domain.servicios.normalizacion import normalizar_dci, variantes_inn
from ...puertos.agencias import RespuestaAgencia

_BASE = "https://api.fda.gov/drug/label.json"
_CANDIDATOS = 10
_MAX_INDICACION = 2000


#: Separadores con que las agencias listan los principios activos de un combinado.
#: openFDA etiqueta en mayusculas ("SITAGLIPTIN AND METFORMIN HYDROCHLORIDE"), asi
#: que la division tiene que hacerse sin distinguir mayusculas: de lo contrario un
#: producto combinado se cuenta como monoingrediente y pasa el filtro.
_SEPARADORES = re.compile(r"\s+and\s+|\s+y\s+|\s*[,;/+]\s*", re.IGNORECASE)


def _ingredientes(registro: dict[str, Any]) -> list[str]:
    nombres = (registro.get("openfda") or {}).get("generic_name") or []
    partes: list[str] = []
    for nombre in nombres:
        for parte in _SEPARADORES.split(str(nombre)):
            normalizado = normalizar_dci(parte)
            if normalizado:
                partes.append(normalizado)
    return partes


def _indicacion(registro: dict[str, Any]) -> str | None:
    textos = registro.get("indications_and_usage") or []
    for texto in textos:
        limpio = str(texto).strip()
        if limpio:
            return limpio[:_MAX_INDICACION]
    return None


class AgenciaOpenFDA:
    def __init__(self, timeout: float = 20.0) -> None:
        self._timeout = timeout

    @property
    def nombre(self) -> str:
        return "FDA"

    def consultar(self, principio_activo: str) -> RespuestaAgencia:
        """Busca la molecula probando las variantes de INN (espanol e ingles)."""
        ultima = self._vacia(
            self._url(principio_activo), "Sin coincidencias en openFDA"
        )
        for variante in variantes_inn(principio_activo) or (principio_activo,):
            respuesta = self._consultar_termino(variante, principio_activo)
            if respuesta.encontrada:
                return respuesta
            ultima = respuesta
        return ultima

    def _url(self, termino: str) -> str:
        return (
            f"{_BASE}?search=openfda.generic_name:%22"
            f"{termino.replace(' ', '+')}%22&limit={_CANDIDATOS}"
        )

    def _consultar_termino(
        self, termino: str, principio_activo: str
    ) -> RespuestaAgencia:
        consulta = f'openfda.generic_name:"{termino}"'
        url = self._url(termino)
        try:
            respuesta = httpx.get(
                _BASE,
                params={"search": consulta, "limit": _CANDIDATOS},
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            return self._vacia(url, f"Error de consulta a openFDA: {exc}")

        if respuesta.status_code == 404:
            return self._vacia(url, "Sin coincidencias en openFDA")
        if respuesta.status_code != 200:
            return self._vacia(
                url, f"openFDA respondio HTTP {respuesta.status_code}"
            )

        resultados = respuesta.json().get("results") or []
        if not resultados:
            return self._vacia(url, "Sin coincidencias en openFDA")

        elegido, nota = self._elegir(resultados, principio_activo)
        if elegido is None:
            return self._vacia(url, nota)

        openfda = elegido.get("openfda") or {}
        marcas = openfda.get("brand_name") or []

        return RespuestaAgencia(
            agencia=self.nombre,
            encontrada=True,
            fecha_aprobacion=None,
            indicacion_aprobada=_indicacion(elegido),
            url_fuente=url,
            nombre_comercial=marcas[0] if marcas else None,
            observaciones=(
                f"{nota} openFDA expone el etiquetado vigente; la fecha de "
                f"aprobacion original debe verificarse en Drugs@FDA."
            ).strip(),
        )

    def _elegir(
        self, resultados: list[dict[str, Any]], principio_activo: str
    ) -> tuple[dict[str, Any] | None, str]:
        """Escoge la etiqueta mas representativa del principio activo consultado.

        Prioridad: monoingrediente con indicacion > monoingrediente sin
        indicacion > combinado con indicacion. Nunca se devuelve un combinado
        sin advertirlo de forma explicita en las observaciones.
        """
        objetivos = set(variantes_inn(principio_activo))

        mono_con_ind: list[dict[str, Any]] = []
        mono_sin_ind: list[dict[str, Any]] = []
        combinados: list[dict[str, Any]] = []

        for registro in resultados:
            ingredientes = _ingredientes(registro)
            if not objetivos & set(ingredientes):
                continue
            if len(ingredientes) == 1:
                (mono_con_ind if _indicacion(registro) else mono_sin_ind).append(registro)
            elif _indicacion(registro):
                combinados.append(registro)

        if mono_con_ind:
            return mono_con_ind[0], ""
        if mono_sin_ind:
            return (
                mono_sin_ind[0],
                "El registro hallado no incluye la seccion de indicaciones; "
                "requiere verificacion directa del evaluador.",
            )
        if combinados:
            ingredientes = ", ".join(_ingredientes(combinados[0]))
            return (
                combinados[0],
                f"ADVERTENCIA: solo se hallaron etiquetas de producto combinado "
                f"({ingredientes}). La indicacion mostrada NO corresponde al "
                f"principio activo aislado.",
            )
        return None, (
            f"Se hallaron registros en openFDA pero ninguno cuyo principio activo "
            f"corresponda a '{principio_activo}'."
        )

    def _vacia(self, url: str, observaciones: str) -> RespuestaAgencia:
        return RespuestaAgencia(
            agencia=self.nombre,
            encontrada=False,
            fecha_aprobacion=None,
            indicacion_aprobada=None,
            url_fuente=url,
            observaciones=observaciones,
        )
