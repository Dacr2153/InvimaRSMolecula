"""Errores del nucleo de auditoria, compartidos por todos los agentes."""

from invima_a1.domain.errores import DatoNoDisponibleError, ErrorDominio


class EspecificacionInvalidaError(ErrorDominio):
    """Se construyo una especificacion sin limites ni valor esperado.

    Una especificacion vacia es peor que ninguna: aparenta que hubo contraste
    cuando no habia contra que contrastar.
    """


class UnidadIncompatibleError(ErrorDominio):
    """Se intento comparar una medicion con una especificacion en otra unidad."""


class SerieInsuficienteError(ErrorDominio):
    """Se pidio estadistica de dispersion sobre menos de dos observaciones."""


class SalidaConclusivaError(ErrorDominio):
    """El payload de salida contenia vocabulario decisorio.

    Barrera tecnica del articulo 7.1: si el agente esta a punto de decir que un
    expediente "cumple" o merece "aprobacion", la corrida falla en vez de
    entregar una opinion que solo le corresponde al evaluador.
    """


__all__ = [
    "ErrorDominio",
    "DatoNoDisponibleError",
    "EspecificacionInvalidaError",
    "UnidadIncompatibleError",
    "SerieInsuficienteError",
    "SalidaConclusivaError",
]
