"""Entidades del dominio.

El agregado raiz es Expediente: concentra el estado, exige la decision humana
antes de enrutar y acumula la traza de auditoria.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum

from .auditoria import EventoAuditoria, TipoEvento
from .errores import TransicionIlegalError
from .estados import DecisionHumana, EstadoExpediente, validar_transicion
from .valores import Dato, Dinero, Traza


@dataclass(frozen=True, slots=True)
class Solicitante:
    nombre_titular: Dato[str]
    representante_colombia: Dato[str]
    nit_representante: Dato[str]


@dataclass(frozen=True, slots=True)
class Producto:
    nombre: Dato[str]
    principio_activo: Dato[str]
    concentracion: Dato[str]
    forma_farmaceutica: Dato[str]
    indicacion_solicitada: Dato[str]


@dataclass(frozen=True, slots=True)
class Pago:
    """Datos de pago declarados en el formulario ASS-RSA-FM113."""

    comprobante_numero: Dato[str]
    codigo_tarifa: Dato[str]
    valor_pagado: Dato[Dinero]


@dataclass(frozen=True, slots=True)
class Tarifa:
    """Registro oficial de tarifas. Fuente de verdad contra la que se valida el pago."""

    codigo: str
    concepto: str
    valor_esperado: Dinero


@dataclass(frozen=True, slots=True)
class TransaccionBancaria:
    """Registro de la base transaccional local contra el que se cruza el comprobante."""

    comprobante_numero: str
    valor_recibido: Dinero
    fecha: date


class TipoCertificado(StrEnum):
    CPP = "CPP"
    """Certificado de Producto Farmaceutico (formato OMS)."""
    CVL = "CVL"
    """Certificado de Venta Libre."""


@dataclass(frozen=True, slots=True)
class CertificadoInternacional:
    tipo: TipoCertificado
    numero: Dato[str]
    pais_emisor: Dato[str]
    autoridad_emisora: Dato[str]


@dataclass(frozen=True, slots=True)
class AprobacionAgencia:
    """Aprobacion otorgada por una agencia de referencia.

    `origen_declarado` distingue lo que dijo el solicitante de lo que el sistema
    verifico contra la fuente publica. Nunca se mezclan.
    """

    agencia: str
    fecha_aprobacion: Dato[date]
    indicacion_aprobada: Dato[str]
    declarada_por_solicitante: bool = False
    verificada_en_fuente: bool = False


@dataclass(frozen=True, slots=True)
class EstudioClinico:
    trial_id: str
    fase: Dato[str]
    estatus: Dato[str]
    resultados_disponibles: Dato[bool]
    declarado_por_solicitante: bool = False
    verificado_en_fuente: bool = False


@dataclass(frozen=True, slots=True)
class ContenidoSospechoso:
    """Texto del expediente que parece intentar dar instrucciones al modelo."""

    campo: str
    fragmento: str
    motivo: str
    traza: Traza | None = None


@dataclass(slots=True)
class Expediente:
    """Agregado raiz del tramite de registro sanitario.

    El estado solo avanza por `avanzar_a`, que consulta la maquina de estados.
    Enrutar sin DecisionHumana es tecnicamente imposible.
    """

    radicado: str
    fecha_radicacion: date
    estado: EstadoExpediente = EstadoExpediente.RECIBIDO
    decision_humana: DecisionHumana | None = None
    eventos: list[EventoAuditoria] = field(default_factory=list)

    def avanzar_a(
        self,
        destino: EstadoExpediente,
        momento: datetime,
        decision: DecisionHumana | None = None,
        detalle: str = "",
    ) -> None:
        validar_transicion(self.estado, destino, decision)
        anterior = self.estado
        self.estado = destino
        if decision is not None:
            self.decision_humana = decision
        self.registrar(
            EventoAuditoria(
                momento=momento,
                tipo=TipoEvento.CAMBIO_ESTADO,
                radicado=self.radicado,
                accion=f"Transicion {anterior} -> {destino}",
                resultado=detalle or "Aplicada",
                actor=decision.usuario if decision else "SISTEMA",
            )
        )

    def registrar_decision_humana(
        self, decision: DecisionHumana, momento: datetime
    ) -> None:
        """Unica puerta de salida del estado PENDIENTE_VALIDACION_HUMANA."""
        self.registrar(
            EventoAuditoria(
                momento=momento,
                tipo=TipoEvento.DECISION_HUMANA,
                radicado=self.radicado,
                accion=f"Decision del evaluador: {decision.sentido}",
                resultado=decision.observaciones or "Sin observaciones",
                actor=decision.usuario,
                detalles={"campos_corregidos": list(decision.campos_corregidos)},
            )
        )
        self.avanzar_a(decision.estado_resultante, momento, decision=decision)

    def registrar(self, evento: EventoAuditoria) -> None:
        self.eventos.append(evento)

    @property
    def esta_pendiente_de_humano(self) -> bool:
        return self.estado is EstadoExpediente.PENDIENTE_VALIDACION_HUMANA

    def exigir_decision_humana(self) -> DecisionHumana:
        if self.decision_humana is None:
            raise TransicionIlegalError(
                "El expediente no cuenta con decision de un servidor publico competente"
            )
        return self.decision_humana
