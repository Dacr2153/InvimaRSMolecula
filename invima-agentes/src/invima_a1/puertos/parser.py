"""Puerto de ingesta documental: PDF -> Markdown estructurado con trazabilidad."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class SeccionDocumento:
    """Fragmento del documento con su ubicacion, para poder citar el folio."""

    titulo: str
    contenido: str
    pagina: int
    modulo: str = "Modulo 1"


@dataclass(frozen=True, slots=True)
class DocumentoParseado:
    nombre_archivo: str
    markdown: str
    secciones: tuple[SeccionDocumento, ...]
    paginas: int

    def texto_de(self, titulo: str) -> str | None:
        for seccion in self.secciones:
            if titulo.lower() in seccion.titulo.lower():
                return seccion.contenido
        return None


class DocumentoParserPort(Protocol):
    """Convierte un PDF (nativo o escaneado) en Markdown conservando la jerarquia."""

    def parsear(self, ruta: Path) -> DocumentoParseado: ...
