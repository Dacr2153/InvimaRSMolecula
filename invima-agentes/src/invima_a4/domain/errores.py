"""Errores del dominio del A4. Definidos en el nucleo, reexportados aqui."""

from invima_nucleo.errores import (
    DatoNoDisponibleError,
    ErrorDominio,
    EspecificacionInvalidaError,
    SalidaConclusivaError,
    SerieInsuficienteError,
    UnidadIncompatibleError,
)

__all__ = [
    "ErrorDominio",
    "DatoNoDisponibleError",
    "EspecificacionInvalidaError",
    "UnidadIncompatibleError",
    "SerieInsuficienteError",
    "SalidaConclusivaError",
]
