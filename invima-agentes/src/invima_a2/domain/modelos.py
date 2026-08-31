"""Entidades juridicas del Modulo 1.

Cada documento se modela con los campos que la norma exige verificar, y nada
mas. Todos son Dato[T]: un certificado del que no se pudo leer la fecha no trae
una fecha inventada, trae NO_SUMINISTRADO con la traza de que se busco.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from .estados import DecisionHumana, EstadoDictamen, validar_transicion
from .valores import Dato


class RolFabricante(StrEnum):
    """Roles que un certificado de BPM puede acreditar.

    Estan separados porque un mismo expediente suele traer dos plantas distintas:
    la que produce la sustancia activa y la que llena el producto terminado. Que
    un BPM ampare una no dice nada de la otra.
    """

    SUSTANCIA_ACTIVA = "Fabricante de Sustancia Activa"
    PRODUCTO_TERMINADO = "Fabricante de Producto Terminado"
    ACONDICIONADOR = "Acondicionador"
    INDETERMINADO = "Rol no declarado"


@dataclass(frozen=True, slots=True)
class PoderEspecial:
    """Poder otorgado al representante en Colombia para tramitar ante el INVIMA."""

    otorgante: Dato[str]
    apoderado: Dato[str]
    nit_apoderado: Dato[str]
    apostilla_presente: Dato[bool]
    autoridad_apostilla: Dato[str]
    traductor_oficial: Dato[str]
    facultades: Dato[str]


@dataclass(frozen=True, slots=True)
class CertificadoExistencia:
    """Certificado de existencia y representacion legal de la Camara de Comercio."""

    razon_social: Dato[str]
    nit: Dato[str]
    representante_legal: Dato[str]
    fecha_expedicion: Dato[date]
    camara: Dato[str]


@dataclass(frozen=True, slots=True)
class CertificadoBPM:
    """Certificado de Buenas Practicas de Manufactura de una planta."""

    fabricante: Dato[str]
    pais: Dato[str]
    rol_declarado: Dato[str]
    fecha_emision: Dato[date]
    fecha_vencimiento: Dato[date]
    autoridad_emisora: Dato[str]


@dataclass(frozen=True, slots=True)
class MatrizResponsabilidades:
    """Quien es quien segun el formulario ASS-RSA-FM113.

    Es la contraparte declarativa de los certificados de BPM. El A2 los trata
    como dos fuentes independientes, igual que el A1 trata el check normativo del
    solicitante frente al Manual: cuando discrepan, se muestran ambas.
    """

    titular: Dato[str]
    fabricante_sustancia_activa: Dato[str]
    fabricante_producto_terminado: Dato[str]
    importador: Dato[str]


@dataclass(frozen=True, slots=True)
class ExpedienteLegal:
    """Los documentos juridicos del Modulo 1, tal como se leyeron del expediente."""

    poder: PoderEspecial | None = None
    certificado_existencia: CertificadoExistencia | None = None
    certificados_bpm: tuple[CertificadoBPM, ...] = ()
    matriz: MatrizResponsabilidades | None = None
    nit_formulario: Dato[str] | None = None


@dataclass(frozen=True, slots=True)
class PerfilProducto:
    """Senales del expediente que determinan la dimension del producto."""

    forma_de_la_sustancia: Dato[str] | None = None
    sistema_de_expresion: Dato[str] | None = None
    banco_celular: Dato[str] | None = None
    producto_referencia: Dato[str] | None = None
    modulos_presentes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(slots=True)
class Dictamen:
    """Agregado del A2: el estado del dictamen y la firma que lo movio.

    Mutable a proposito, igual que `Expediente` en el A1: es lo unico del dominio
    que cambia con el tiempo. Todo lo demas son valores inmutables.
    """

    radicado: str
    fecha_radicacion: date
    estado: EstadoDictamen = EstadoDictamen.RECIBIDO_DE_A1
    decision: DecisionHumana | None = None

    def avanzar_a(
        self, destino: EstadoDictamen, decision: DecisionHumana | None = None
    ) -> None:
        validar_transicion(self.estado, destino, decision)
        self.estado = destino
        if decision is not None:
            self.decision = decision

    @property
    def esta_pendiente_de_humano(self) -> bool:
        return self.estado in (
            EstadoDictamen.PENDIENTE_VALIDACION_COORDINADOR,
            EstadoDictamen.RETENIDO_POR_ALERTA_CRITICA,
        )
