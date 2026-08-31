"""Puertos: interfaces que el dominio necesita del mundo exterior.

Solo Protocols. Ninguna implementacion, ninguna dependencia de librerias externas.
Cambiar de Gemini a otro modelo, o de SQLite a PostgreSQL, es escribir un adaptador
nuevo; el nucleo no se entera.
"""

from .agencias import AgenciaReferenciaPort, RespuestaAgencia
from .auditoria import AuditLogPort
from .ensayos import EnsayosClinicosPort, RespuestaEnsayo
from .extractor import ExtractorMetadatosPort
from .normas import NormasFarmacologicasPort
from .parser import DocumentoParseado, DocumentoParserPort, SeccionDocumento
from .repositorio import RepositorioExpedientePort
from .tarifas import TarifarioPort, TransaccionesPort

__all__ = [
    "AgenciaReferenciaPort",
    "AuditLogPort",
    "DocumentoParseado",
    "DocumentoParserPort",
    "EnsayosClinicosPort",
    "ExtractorMetadatosPort",
    "NormasFarmacologicasPort",
    "RepositorioExpedientePort",
    "RespuestaAgencia",
    "RespuestaEnsayo",
    "SeccionDocumento",
    "TarifarioPort",
    "TransaccionesPort",
]
