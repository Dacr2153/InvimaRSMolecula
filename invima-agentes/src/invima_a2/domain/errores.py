"""Errores del dominio del Agente 2."""

from invima_a1.domain.errores import (
    DatoNoDisponibleError,
    ErrorDominio,
    TransicionIlegalError,
)


class ExpedienteNoValidableError(ErrorDominio):
    """Se intento validar legalmente un expediente que el A1 no entrego apto.

    Si el A1 suspendio por inconsistencia de pago, el tramite no puede repartirse
    y extraer los documentos legales seria gasto sin destino. El corte temprano
    del A1 se respeta aguas abajo en vez de reabrirse.
    """


class SalidaConclusivaError(ErrorDominio):
    """El payload de salida contenia vocabulario decisorio.

    Barrera tecnica del articulo 7.1: si el agente esta a punto de decir que un
    poder "es valido" o que un expediente "cumple", la corrida falla en vez de
    entregar una calificacion que solo le corresponde al evaluador.
    """


__all__ = [
    "ErrorDominio",
    "DatoNoDisponibleError",
    "TransicionIlegalError",
    "ExpedienteNoValidableError",
    "SalidaConclusivaError",
]
