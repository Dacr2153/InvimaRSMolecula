"""Parser offline: lee el sidecar Markdown que acompana a cada PDF de fixture.

El generador de fixtures escribe `<nombre>.pdf` y `<nombre>.md` con el mismo
contenido. En modo offline se usa el Markdown: cero dependencias, cero costo,
resultado identico en cada corrida.
"""

from __future__ import annotations

import re
from pathlib import Path

from ...puertos.parser import DocumentoParseado, SeccionDocumento

_ENCABEZADO = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_MARCA_PAGINA = re.compile(r"<!--\s*pagina:\s*(\d+)\s*-->")


class ParserSidecarMarkdown:
    """Implementa DocumentoParserPort leyendo el .md hermano del PDF."""

    def parsear(self, ruta: Path) -> DocumentoParseado:
        sidecar = ruta if ruta.suffix == ".md" else ruta.with_suffix(".md")
        if not sidecar.exists():
            raise FileNotFoundError(
                f"No hay sidecar Markdown para {ruta.name}. Genera los fixtures con "
                f"tools/generar_dossier_sintetico.py o usa el parser de Docling."
            )
        markdown = sidecar.read_text(encoding="utf-8")
        return DocumentoParseado(
            nombre_archivo=ruta.name,
            markdown=markdown,
            secciones=self._secciones(markdown),
            paginas=self._paginas(markdown),
        )

    def _secciones(self, markdown: str) -> tuple[SeccionDocumento, ...]:
        encabezados = list(_ENCABEZADO.finditer(markdown))
        secciones: list[SeccionDocumento] = []
        for indice, encabezado in enumerate(encabezados):
            inicio = encabezado.end()
            fin = (
                encabezados[indice + 1].start()
                if indice + 1 < len(encabezados)
                else len(markdown)
            )
            cuerpo = markdown[inicio:fin]
            marca = _MARCA_PAGINA.search(markdown[: encabezado.start()][::-1])
            pagina = 1
            marcas = _MARCA_PAGINA.findall(markdown[: encabezado.start()])
            if marcas:
                pagina = int(marcas[-1])
            secciones.append(
                SeccionDocumento(
                    titulo=encabezado.group(1).strip(),
                    contenido=cuerpo.strip(),
                    pagina=pagina,
                )
            )
        return tuple(secciones)

    def _paginas(self, markdown: str) -> int:
        marcas = _MARCA_PAGINA.findall(markdown)
        return max((int(m) for m in marcas), default=1)
