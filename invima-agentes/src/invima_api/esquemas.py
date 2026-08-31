"""Modelos de request y response del contrato (infra/CONTRATO-API.md).

Convencion: snake_case adentro, camelCase en el JSON. El alias lo genera
pydantic, no se escribe a mano campo por campo.

Regla que ordena este modulo: ningun modelo de respuesta tiene un campo
`aprobado`, `cumple`, `conforme` ni `puntaje`. El unico sentido de decision del
contrato vive en RespuestaDecision, y lo escribe una persona con nombre.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer
from pydantic.alias_generators import to_camel


class Modelo(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


# ------------------------------------------------------------------ catalogos


class ItemCatalogo(Modelo):
    id: str
    etiqueta: str
    descripcion: str = ""


class ItemTarifa(Modelo):
    codigo: str
    concepto: str
    valor: Decimal

    @field_serializer("valor")
    def _valor(self, valor: Decimal) -> str:
        return f"{valor:.2f}"


class ItemMetodoPago(Modelo):
    id: str
    etiqueta: str


class ItemDocumentoRequerido(Modelo):
    id: str
    nombre: str
    obligatorio: bool
    folio_destino: str | None = None


class ItemModuloCtd(Modelo):
    id: str
    titulo: str
    documentos: list[ItemDocumentoRequerido] = Field(default_factory=list)


class Catalogos(Modelo):
    tipos_tramite: list[ItemCatalogo]
    tipos_producto: list[ItemCatalogo]
    tarifas: list[ItemTarifa]
    metodos_pago: list[ItemMetodoPago]
    modulos_ctd: list[ItemModuloCtd]


# ----------------------------------------------------------------- solicitud


class CrearSolicitud(Modelo):
    solicitante_nit: str | None = None


class ActualizarSolicitud(Modelo):
    tipo_tramite: str | None = None
    tipo_producto: str | None = None
    datos_declarados: dict[str, Any] | None = None
    tarifa_codigo: str | None = None
    metodo_pago: str | None = None
    comprobante: str | None = None
    valor_pagado: Decimal | None = None
    fecha_pago: date | None = None


class DocumentoSolicitud(Modelo):
    requerido_id: str
    nombre_archivo: str
    tamano_bytes: int
    sha256: str
    cargado_en: datetime


class Solicitud(Modelo):
    id: UUID
    estado: str
    tipo_tramite: str | None = None
    tipo_producto: str | None = None
    datos_declarados: dict[str, Any] = Field(default_factory=dict)
    tarifa_codigo: str | None = None
    metodo_pago: str | None = None
    comprobante: str | None = None
    valor_pagado: Decimal | None = None
    fecha_pago: date | None = None
    radicado: str | None = None
    radicada_en: datetime | None = None
    documentos: list[DocumentoSolicitud] = Field(default_factory=list)
    enlaces: list[EnlaceEvidencia] = Field(default_factory=list)

    @field_serializer("valor_pagado")
    def _valor_pagado(self, valor: Decimal | None) -> str | None:
        return None if valor is None else f"{valor:.2f}"


class EnlaceEvidencia(Modelo):
    id: UUID
    url: str
    titulo: str = ""
    tipo: str = "OTRO"
    referencia: str = ""
    creado_en: datetime


class CrearEnlace(Modelo):
    url: str
    titulo: str = ""


class ValidacionPago(Modelo):
    verificado: bool
    resultado: str
    inconsistencias: list[dict[str, Any]] = Field(default_factory=list)


class ResultadoRadicacion(Modelo):
    radicado: str
    fecha_radicacion: date
    estado: str
    suspendido: bool
    tipo_tramite: str
    tipo_producto: str
    validacion_pago: ValidacionPago
    advertencia: str


# ---------------------------------------------------------------- expediente


class ItemBandeja(Modelo):
    radicado: str
    producto: str
    principio_activo: str
    titular: str
    tramite: str
    estado: str
    estado_label: str
    dias_en_cola: int
    ruta_recomendada: str


class DocumentoExpediente(Modelo):
    requerido_id: str
    nombre: str
    modulo: str
    nombre_archivo: str
    tamano_bytes: int
    sha256: str
    cargado_en: datetime


class DecisionHumanaVista(Modelo):
    usuario: str
    sentido: str
    momento: datetime
    observaciones: str = ""


class EventoVista(Modelo):
    momento: datetime
    tipo: str
    accion: str
    resultado: str
    actor: str


class ExpedienteDetalle(Modelo):
    radicado: str
    estado: str
    estado_label: str
    producto: str
    principio_activo: str
    titular: str
    tramite: str
    fecha_radicacion: date
    payload: dict[str, Any]
    documentos: list[DocumentoExpediente] = Field(default_factory=list)
    decision_humana: DecisionHumanaVista | None = None
    puede_decidir: bool = False
    eventos: list[EventoVista] = Field(default_factory=list)


class SolicitudDecision(Modelo):
    usuario: str
    sentido: str
    observaciones: str = ""
    campos_corregidos: list[str] = Field(default_factory=list)


class RespuestaDecision(Modelo):
    estado: str
    usuario_responsable: str
    sentido: str
    firma_timestamp: datetime


# ------------------------------------------------------------------- agentes


class InformeAgente(Modelo):
    """La corrida de un agente sobre el expediente, tal como la ve el evaluador.

    `payload` es el informe completo del agente, con trazabilidad campo por
    campo. `resumen` es la sintesis para la tarjeta. Ninguno contiene un
    concepto: los estados terminales de los agentes son siempre "pendiente de
    validacion" de un humano.
    """

    agente: str
    nombre: str
    estado: str
    iniciado_en: datetime | None = None
    terminado_en: datetime | None = None
    duracion_ms: int | None = None
    modelo: str = ""
    resumen: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)
    error: str = ""


# ----------------------------------------------------------------- checklist


class ItemChecklist(Modelo):
    id: UUID
    texto: str
    verificado: bool
    origen: str
    orden: int
    verificado_por: str | None = None
    verificado_en: datetime | None = None


class CrearItemChecklist(Modelo):
    texto: str


class ActualizarItemChecklist(Modelo):
    verificado: bool
    usuario: str


# ------------------------------------------------------------------- fuentes


class FuenteExterna(Modelo):
    id: UUID
    fuente: str
    titulo: str
    tipo: str = ""
    pais: str = ""
    fecha: str = ""
    url: str = ""
    encontrada: bool
    observaciones: str = ""
    vinculada: bool = False


class VincularFuente(Modelo):
    vinculada: bool
    usuario: str


# ------------------------------------------------------------------ consultas


class ConsultaSugerida(Modelo):
    id: str
    pregunta: str


class Consulta(Modelo):
    id: UUID
    pregunta: str
    respuesta: str
    cita: str = ""
    url: str = ""
    encontrada: bool
    momento: datetime


class CrearConsulta(Modelo):
    pregunta: str
    usuario: str = ""
