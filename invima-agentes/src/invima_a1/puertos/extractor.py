"""Puerto del modelo de lenguaje.

Unico punto del sistema donde entra un LLM. Su contrato es estrecho a proposito:
recibe texto y un esquema, devuelve un diccionario. No razona, no decide, no
redacta conclusiones. Cambiar Gemini por otro modelo es implementar esta interfaz.
"""

from __future__ import annotations

from typing import Any, Protocol


class ExtractorMetadatosPort(Protocol):
    def extraer(
        self,
        contenido: str,
        esquema: dict[str, Any],
        instruccion: str,
    ) -> dict[str, Any]:
        """Mapea texto libre a la estructura descrita por `esquema`.

        Regla que toda implementacion debe respetar: si un campo no aparece
        explicitamente en el contenido, se devuelve null. Nunca se infiere.
        """
        ...

    @property
    def identificador_modelo(self) -> str:
        """Modelo y version usados, para que quede en el log de auditoria."""
        ...
