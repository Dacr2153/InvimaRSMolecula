"""Puertos del Agente 3.

Los puertos de parseo documental, extraccion por modelo y log de auditoria se
reusan del nucleo: el A3 lee los mismos PDF y escribe al mismo log append-only.
"""

from invima_a1.puertos.auditoria import AuditLogPort
from invima_a1.puertos.extractor import ExtractorMetadatosPort
from invima_a1.puertos.parser import DocumentoParseado, DocumentoParserPort

__all__ = [
    "AuditLogPort",
    "ExtractorMetadatosPort",
    "DocumentoParserPort",
    "DocumentoParseado",
]
