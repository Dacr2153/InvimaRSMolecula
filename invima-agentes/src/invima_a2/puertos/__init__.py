"""Puertos del Agente 2.

Los puertos de parseo documental, extraccion por modelo y log de auditoria se
reusan del nucleo: el A2 lee los mismos folios y escribe al mismo log
append-only, bajo el mismo radicado. El expediente queda reconstruible de punta
a punta atravesando los dos agentes.
"""

from invima_a1.puertos.auditoria import AuditLogPort
from invima_a1.puertos.extractor import ExtractorMetadatosPort
from invima_a1.puertos.parser import DocumentoParseado, DocumentoParserPort

from .expediente_a1 import ExpedienteA1Port

__all__ = [
    "AuditLogPort",
    "ExtractorMetadatosPort",
    "DocumentoParserPort",
    "DocumentoParseado",
    "ExpedienteA1Port",
]
