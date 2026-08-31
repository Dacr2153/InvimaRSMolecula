"""Puertos del Agente 4.

El parseo documental, la extraccion por modelo y el log de auditoria se reusan
del nucleo del A1: el A4 lee los mismos PDF y escribe al mismo log append-only.
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
