"""Errores del dominio."""


class ErrorDominio(Exception):
    """Raiz de todos los errores del nucleo."""


class TransicionIlegalError(ErrorDominio):
    """Se intento una transicion de estado no permitida por la maquina de estados.

    El caso mas importante: intentar enrutar un expediente sin decision humana previa.
    Las reglas de la Hackaton prohiben que la IA adopte decisiones administrativas;
    esta excepcion es la barrera tecnica que hace imposible saltarse al evaluador.
    """


class DatoNoDisponibleError(ErrorDominio):
    """Se pidio el valor de un Dato que no fue suministrado en el expediente."""


class OrigenNoDeclaradoError(ErrorDominio):
    """Se intento construir un Dato sin declarar de donde proviene."""
