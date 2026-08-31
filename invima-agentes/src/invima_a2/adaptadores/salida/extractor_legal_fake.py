"""Extractor determinista de documentos legales, para desarrollo y pruebas.

Mismo papel que `ExtractorDeterminista` en el A1: permite correr el agente
completo sin red, sin API key y sin costo. Lee el anexo legal en Markdown que
produce `tools/generar_anexo_legal.py` y devuelve la misma estructura que
devolveria el modelo.

No es un "modelo simulado": es un parser. Que el contrato del puerto sea
estrecho (texto + esquema -> dict) es lo que hace posible sustituir un LLM por
veinte lineas de regex sin que el dominio se entere.
"""

from __future__ import annotations

import re
from typing import Any

from invima_a1.domain.servicios.normalizacion import sin_tildes

_CAMPO = "|".join(
    [
        r"Otorgante",
        r"Apoderado",
        r"NIT del Apoderado",
        r"Apostilla",
        r"Autoridad de Apostilla",
        r"Traductor Oficial",
        r"Facultades",
        r"Razon Social",
        r"NIT de la Sociedad",
        r"Representante Legal",
        r"Fecha de Expedicion",
        r"Camara de Comercio",
        r"Titular",
        r"Fabricante de Sustancia Activa",
        r"Fabricante de Producto Terminado",
        r"Importador",
        r"Forma de la Sustancia",
        r"Sistema de Expresion",
        r"Banco Celular",
        r"Producto de Referencia",
        r"Modulos Presentes",
    ]
)
_LINEA = re.compile(rf"^\s*(?:\*\*)?({_CAMPO})(?:\*\*)?\s*:\s*(.+?)\s*$", re.MULTILINE)
_MARCA_PAGINA = re.compile(r"<!--\s*pagina:\s*(\d+)\s*-->")
_ENCABEZADO = re.compile(r"^#{1,3}\s*(.+?)\s*$", re.MULTILINE)

#: Secciones del anexo legal cuyas etiquetas este extractor puede leer.
#: Todo lo que este fuera de ellas se ignora, incluido el propio ASS-RSA-FM113
#: que viaja en la misma carpeta. Sin este alcance, una etiqueta repetida entre
#: dos documentos hace que el ultimo leido pise al primero en silencio.
_SECCIONES_LEGALES = (
    "poder especial",
    "certificado de existencia",
    "certificados de buenas practicas",
    "matriz de responsabilidades",
    "perfil del producto",
)
_FILA_BPM = re.compile(
    r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(Fabricante de [^|]+?|Acondicionador|-)\s*\|"
    r"\s*([0-9]{4}-[0-9]{2}-[0-9]{2}|-)\s*\|\s*([0-9]{4}-[0-9]{2}-[0-9]{2}|-)\s*\|"
    r"\s*([^|]+?)\s*\|\s*$",
    re.MULTILINE,
)

_AFIRMATIVOS = {"presente", "si", "yes", "true", "adjunta", "adjunto"}
_NEGATIVOS = {"ausente", "no", "false", "no aporta", "no suministrada", "-"}


def _limpiar(valor: str) -> str | None:
    texto = valor.strip().strip("*").strip()
    if not texto or texto in {"-", "No suministrado", "No suministrada"}:
        return None
    return texto


class ExtractorLegalDeterminista:
    """Implementa ExtractorMetadatosPort sin modelo."""

    @property
    def identificador_modelo(self) -> str:
        return "extractor-legal-determinista-offline (sin LLM)"

    def extraer(
        self, contenido: str, esquema: dict[str, Any], instruccion: str
    ) -> dict[str, Any]:
        campos = self._campos(contenido)

        def v(etiqueta: str) -> tuple[str | None, int | None]:
            crudo = campos.get(etiqueta)
            if crudo is None:
                return None, None
            return _limpiar(crudo[0]), crudo[1]

        otorgante, pag_poder = v("Otorgante")
        apoderado, _ = v("Apoderado")
        nit_apoderado, _ = v("NIT del Apoderado")
        apostilla_texto, _ = v("Apostilla")
        autoridad_apostilla, _ = v("Autoridad de Apostilla")
        traductor, _ = v("Traductor Oficial")
        facultades, _ = v("Facultades")

        apostilla: bool | None = None
        if apostilla_texto is not None:
            normal = apostilla_texto.strip().lower()
            if normal in _AFIRMATIVOS:
                apostilla = True
            elif normal in _NEGATIVOS:
                apostilla = False
        elif "Apostilla" in campos or otorgante is not None:
            # El poder existe pero no menciona apostilla: la ausencia de mencion
            # es un false explicito, no un null. La regla de negocio distingue
            # "no aporta poder" de "aporta poder sin apostilla".
            apostilla = False

        razon_social, pag_ccb = v("Razon Social")
        nit, _ = v("NIT de la Sociedad")
        representante, _ = v("Representante Legal")
        expedicion, _ = v("Fecha de Expedicion")
        camara, _ = v("Camara de Comercio")

        titular, pag_matriz = v("Titular")
        fab_activa, _ = v("Fabricante de Sustancia Activa")
        fab_terminado, _ = v("Fabricante de Producto Terminado")
        importador, _ = v("Importador")

        forma, pag_perfil = v("Forma de la Sustancia")
        expresion, _ = v("Sistema de Expresion")
        banco, _ = v("Banco Celular")
        referencia, _ = v("Producto de Referencia")
        modulos_texto, _ = v("Modulos Presentes")
        modulos = (
            [m.strip() for m in modulos_texto.split(",") if m.strip()]
            if modulos_texto
            else []
        )

        return {
            "poder_especial": {
                "otorgante": otorgante,
                "apoderado": apoderado,
                "nit_apoderado": nit_apoderado,
                "apostilla_presente": apostilla,
                "autoridad_apostilla": autoridad_apostilla,
                "traductor_oficial": traductor,
                "facultades": facultades,
                "pagina": pag_poder,
            },
            "certificado_existencia": {
                "razon_social": razon_social,
                "nit": nit,
                "representante_legal": representante,
                "fecha_expedicion": expedicion,
                "camara": camara,
                "pagina": pag_ccb,
            },
            "certificados_bpm": self._bpm(contenido),
            "matriz_responsabilidades": {
                "titular": titular,
                "fabricante_sustancia_activa": fab_activa,
                "fabricante_producto_terminado": fab_terminado,
                "importador": importador,
                "pagina": pag_matriz,
            },
            "perfil_producto": {
                "forma_de_la_sustancia": forma,
                "sistema_de_expresion": expresion,
                "banco_celular": banco,
                "producto_referencia": referencia,
                "modulos_presentes": modulos,
                "pagina": pag_perfil,
            },
        }

    def _campos(self, contenido: str) -> dict[str, tuple[str, int | None]]:
        campos: dict[str, tuple[str, int | None]] = {}
        for coincidencia in _LINEA.finditer(contenido):
            if not self._en_seccion_legal(contenido, coincidencia.start()):
                continue
            etiqueta, valor = coincidencia.group(1), coincidencia.group(2)
            if etiqueta in campos:
                continue
            campos[etiqueta] = (valor, self._pagina_en(contenido, coincidencia.start()))
        return campos

    def _en_seccion_legal(self, contenido: str, posicion: int) -> bool:
        """Verdadero si la posicion cae bajo un encabezado del anexo legal."""
        encabezados = [m for m in _ENCABEZADO.finditer(contenido) if m.start() < posicion]
        if not encabezados:
            return False
        titulo = sin_tildes(encabezados[-1].group(1)).lower()
        return any(s in titulo for s in _SECCIONES_LEGALES)

    def _pagina_en(self, contenido: str, posicion: int) -> int | None:
        marcas = [m for m in _MARCA_PAGINA.finditer(contenido) if m.start() < posicion]
        return int(marcas[-1].group(1)) if marcas else None

    def _bpm(self, contenido: str) -> list[dict[str, Any]]:
        filas: list[dict[str, Any]] = []
        for m in _FILA_BPM.finditer(contenido):
            fabricante, pais, rol, emision, vence, autoridad = (
                _limpiar(g) for g in m.groups()
            )
            if fabricante is None or fabricante.lower() in {"fabricante", "---"}:
                continue
            filas.append(
                {
                    "fabricante": fabricante,
                    "pais": pais,
                    "rol_declarado": rol,
                    "fecha_emision": emision,
                    "fecha_vencimiento": vence,
                    "autoridad_emisora": autoridad,
                    "pagina": self._pagina_en(contenido, m.start()),
                }
            )
        return filas
