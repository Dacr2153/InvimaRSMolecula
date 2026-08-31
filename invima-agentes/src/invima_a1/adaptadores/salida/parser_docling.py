"""Parser real con Docling.

Docling es MIT y corre local: el OCR del expediente no cuesta un centavo. Esta
fue una decision de presupuesto deliberada frente a servicios que cobran por
pagina, dado que un dossier CTD son cientos de paginas.
"""

from __future__ import annotations

from pathlib import Path

from ...puertos.parser import DocumentoParseado, SeccionDocumento


class ParserDocling:
    """Implementa DocumentoParserPort sobre docling."""

    def __init__(self) -> None:
        try:
            from docling.document_converter import DocumentConverter
        except ImportError as exc:  # pragma: no cover - depende del entorno
            raise ImportError(
                "Docling no esta instalado. Instala el extra: uv pip install '.[ocr]' "
                "o usa el modo offline con ParserSidecarMarkdown."
            ) from exc
        self._conversor = DocumentConverter()

    def parsear(self, ruta: Path) -> DocumentoParseado:  # pragma: no cover - I/O real
        resultado = self._conversor.convert(str(ruta))
        documento = resultado.document
        markdown = documento.export_to_markdown()

        secciones: list[SeccionDocumento] = []
        for item, _nivel in documento.iterate_items():
            texto = getattr(item, "text", None)
            if not texto:
                continue
            pagina = 1
            provenencia = getattr(item, "prov", None)
            if provenencia:
                pagina = getattr(provenencia[0], "page_no", 1)
            secciones.append(
                SeccionDocumento(
                    titulo=texto[:80],
                    contenido=texto,
                    pagina=pagina,
                )
            )

        paginas = len(getattr(documento, "pages", {}) or {}) or 1
        return DocumentoParseado(
            nombre_archivo=ruta.name,
            markdown=markdown,
            secciones=tuple(secciones),
            paginas=paginas,
        )
