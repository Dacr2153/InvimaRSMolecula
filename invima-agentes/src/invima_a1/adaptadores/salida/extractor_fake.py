"""Extractor determinista para modo offline y pruebas.

Lee el Markdown de los fixtures con expresiones regulares. Cero red, cero costo,
resultado identico en cada corrida. Toda la suite de tests se apoya en esto, de
modo que desarrollar no consume el credito.

Respeta el mismo contrato que el extractor real: campo ausente, valor null.
"""

from __future__ import annotations

import re
from typing import Any

_CAMPO = "|".join(
    [
        r"Razon Social del Titular",
        r"Representante en Colombia",
        r"NIT",
        r"Nombre del Producto",
        r"Principio Activo",
        r"Concentracion",
        r"Forma Farmaceutica",
        r"Indicacion Solicitada",
        r"Tipo de Tramite",
        r"Modalidad",
        r"Ruta de Estudio",
        r"Comprobante No",
        r"Codigo de Tarifa",
        r"Valor Pagado",
        r"Observaciones",
        r"Tipo de Certificado",
        r"Numero de Certificado",
        r"Pais Emisor",
        r"Autoridad Emisora",
        r"Molecula NO Incluida en Normas Farmacologicas",
    ]
)
_LINEA = re.compile(rf"^\s*(?:\*\*)?({_CAMPO})(?:\*\*)?\s*:\s*(.+?)\s*$", re.MULTILINE)
_MARCA_PAGINA = re.compile(r"<!--\s*pagina:\s*(\d+)\s*-->")
_NCT = re.compile(r"\bNCT\d{8}\b")
_FILA_AGENCIA = re.compile(
    r"^\|\s*(FDA|EMA|MHRA|Health Canada|TGA|PMDA)\s*\|"
    r"\s*([0-9]{4}-[0-9]{2}-[0-9]{2}|No suministrado|-)\s*\|\s*(.+?)\s*\|\s*$",
    re.MULTILINE | re.IGNORECASE,
)


def _pagina_de(markdown: str, posicion: int) -> int | None:
    marcas = _MARCA_PAGINA.findall(markdown[:posicion])
    return int(marcas[-1]) if marcas else None


def _limpiar(valor: str) -> str | None:
    limpio = valor.strip().strip("|").strip()
    if not limpio or limpio.lower() in {"no suministrado", "n/a", "-", "null"}:
        return None
    return limpio


class ExtractorDeterminista:
    """Implementa ExtractorMetadatosPort sin modelo de lenguaje."""

    @property
    def identificador_modelo(self) -> str:
        return "extractor-determinista-offline (sin LLM)"

    def extraer(
        self, contenido: str, esquema: dict[str, Any], instruccion: str
    ) -> dict[str, Any]:
        campos: dict[str, tuple[str, int | None]] = {}
        for coincidencia in _LINEA.finditer(contenido):
            etiqueta = coincidencia.group(1).strip()
            valor = coincidencia.group(2)
            campos[etiqueta] = (valor, _pagina_de(contenido, coincidencia.start()))

        propiedades = esquema.get("properties", {})
        if "solicitante" in propiedades:
            return self._fm113(campos)
        return self._autovalidacion(campos, contenido)

    def _valor(
        self, campos: dict[str, tuple[str, int | None]], etiqueta: str
    ) -> tuple[str | None, int | None]:
        crudo = campos.get(etiqueta)
        if crudo is None:
            return None, None
        return _limpiar(crudo[0]), crudo[1]

    def _fm113(self, campos: dict[str, tuple[str, int | None]]) -> dict[str, Any]:
        titular, pag_sol = self._valor(campos, "Razon Social del Titular")
        representante, _ = self._valor(campos, "Representante en Colombia")
        nit, _ = self._valor(campos, "NIT")

        nombre, pag_pro = self._valor(campos, "Nombre del Producto")
        principio, _ = self._valor(campos, "Principio Activo")
        concentracion, _ = self._valor(campos, "Concentracion")
        forma, _ = self._valor(campos, "Forma Farmaceutica")
        indicacion, _ = self._valor(campos, "Indicacion Solicitada")

        tipo, pag_tra = self._valor(campos, "Tipo de Tramite")
        modalidad, _ = self._valor(campos, "Modalidad")
        ruta, _ = self._valor(campos, "Ruta de Estudio")

        comprobante, pag_pago = self._valor(campos, "Comprobante No")
        codigo, _ = self._valor(campos, "Codigo de Tarifa")
        valor_texto, _ = self._valor(campos, "Valor Pagado")
        observaciones, _ = self._valor(campos, "Observaciones")

        valor_pagado: float | None = None
        if valor_texto:
            limpio = re.sub(r"[^0-9,.]", "", valor_texto).replace(".", "").replace(",", ".")
            try:
                valor_pagado = float(limpio)
            except ValueError:
                valor_pagado = None

        return {
            "solicitante": {
                "nombre_titular": titular,
                "representante_colombia": representante,
                "nit_representante": nit,
                "pagina": pag_sol,
            },
            "producto": {
                "nombre": nombre,
                "principio_activo": principio,
                "concentracion": concentracion,
                "forma_farmaceutica": forma,
                "indicacion_solicitada": indicacion,
                "pagina": pag_pro,
            },
            "tramite": {
                "tipo_tramite": tipo,
                "modalidad": modalidad,
                "ruta_estudio": ruta,
                "pagina": pag_tra,
            },
            "pago": {
                "comprobante_numero": comprobante,
                "codigo_tarifa": codigo,
                "valor_pagado": valor_pagado,
                "pagina": pag_pago,
            },
            "observaciones_texto_libre": observaciones,
        }

    def _autovalidacion(
        self, campos: dict[str, tuple[str, int | None]], contenido: str
    ) -> dict[str, Any]:
        check_texto, pag_check = self._valor(
            campos, "Molecula NO Incluida en Normas Farmacologicas"
        )
        check: bool | None = None
        if check_texto is not None:
            check = check_texto.strip().lower() in {"si", "sí", "x", "true", "marcado"}

        tipo, pag_cert = self._valor(campos, "Tipo de Certificado")
        numero, _ = self._valor(campos, "Numero de Certificado")
        pais, _ = self._valor(campos, "Pais Emisor")
        autoridad, _ = self._valor(campos, "Autoridad Emisora")

        aprobaciones: list[dict[str, Any]] = []
        for fila in _FILA_AGENCIA.finditer(contenido):
            fecha = _limpiar(fila.group(2))
            aprobaciones.append(
                {
                    "agencia": fila.group(1).strip().upper(),
                    "fecha_aprobacion": fecha,
                    "indicacion_aprobada": _limpiar(fila.group(3)),
                    "pagina": _pagina_de(contenido, fila.start()),
                }
            )

        return {
            "check_molecula_no_incluida_en_normas": check,
            "certificado": {
                "tipo": tipo,
                "numero": numero,
                "pais_emisor": pais,
                "autoridad_emisora": autoridad,
                "pagina": pag_cert or pag_check,
            },
            "aprobaciones_declaradas": aprobaciones,
            "nct_ids_declarados": sorted(set(_NCT.findall(contenido))),
        }
