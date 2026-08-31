"""Validacion de la documentacion juridica del Modulo 1.

Motor puro: sin red, sin modelo, sin I/O. Las cuatro reglas que aplica son
aritmetica y comparacion de cadenas, y un evaluador puede leerlas de arriba
abajo y verificar que hacen lo que dicen.

Ninguna funcion de este modulo devuelve "valido" ni "cumple". Devuelven lo que
compararon y lo que encontraron. La calificacion juridica es del evaluador.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ..modelos import (
    CertificadoBPM,
    CertificadoExistencia,
    ExpedienteLegal,
    MatrizResponsabilidades,
    PoderEspecial,
    RolFabricante,
)
from ..valores import Dato, Traza
from .motor_alertas import Alerta, Severidad, TipoAlerta, hay_bloqueo, ordenar
from .razon_social import coinciden_nit, coinciden_razon_social

#: Vigencia maxima del certificado de existencia y representacion legal.
#: La cuenta es contra la fecha de radicacion, no contra la fecha de hoy: un
#: expediente radicado en plazo no vence porque el A2 se corra un mes despues.
DIAS_VIGENCIA_CCB = 30


@dataclass(frozen=True, slots=True)
class VerificacionLegal:
    """Resultado de la validacion documental del Modulo 1."""

    poder: dict[str, Dato[object]]
    certificado_existencia: dict[str, Dato[object]]
    bpm: tuple[dict[str, Dato[object]], ...]
    coherencia_nit: dict[str, Dato[object]]
    alertas: tuple[Alerta, ...]

    @property
    def bloquea_reparto(self) -> bool:
        return hay_bloqueo(self.alertas)


def _traza_legal(seccion: str, campo: str) -> Traza:
    return Traza.en_documento("Modulo 1", seccion, None, campo)


def verificar_poder(poder: PoderEspecial | None) -> tuple[dict, list[Alerta]]:
    """Apostilla y traductor oficial.

    La Convencion de La Haya sustituye la legalizacion consular por la apostilla.
    Un poder otorgado en el exterior sin ella no acredita representacion ante la
    autoridad colombiana, y sin traductor oficial matriculado el texto en otro
    idioma no hace fe. Ambas ausencias son CRITICAS: no son subsanables leyendo
    con mas atencion, hay que pedir el documento otra vez.
    """
    alertas: list[Alerta] = []
    if poder is None:
        alertas.append(
            Alerta(
                tipo=TipoAlerta.DOCUMENTO_FALTANTE,
                severidad=Severidad.CRITICA,
                mensaje="El Modulo 1 no aporta poder especial al representante en Colombia",
                esperado="Poder especial apostillado",
                encontrado="No suministrado",
            )
        )
        return {
            "apostilla_presente": Dato.ausente("Poder especial en el Modulo 1"),
            "traductor_oficial": Dato.ausente("Poder especial en el Modulo 1"),
        }, alertas

    if not (poder.apostilla_presente.presente and poder.apostilla_presente.exigir()):
        alertas.append(
            Alerta(
                tipo=TipoAlerta.PODER_SIN_APOSTILLA,
                severidad=Severidad.CRITICA,
                mensaje=(
                    "El poder especial no acredita sello de apostilla. Sin el, el "
                    "documento no surte efectos ante la autoridad colombiana"
                ),
                esperado="Sello de apostilla de la autoridad competente del pais de origen",
                encontrado="Ausente en el documento",
                traza=poder.apostilla_presente.traza,
            )
        )

    if not poder.traductor_oficial.presente:
        alertas.append(
            Alerta(
                tipo=TipoAlerta.PODER_SIN_TRADUCTOR,
                severidad=Severidad.CRITICA,
                mensaje=(
                    "El poder no identifica traductor oficial matriculado. Una "
                    "traduccion sin responsable no hace fe del contenido"
                ),
                esperado="Nombre y matricula del traductor oficial",
                encontrado="No suministrado",
                traza=_traza_legal("Poder especial", "Traductor oficial"),
            )
        )

    return {
        "otorgante": poder.otorgante,
        "apoderado": poder.apoderado,
        "apostilla_presente": poder.apostilla_presente,
        "autoridad_apostilla": poder.autoridad_apostilla,
        "traductor_oficial": poder.traductor_oficial,
        "facultades": poder.facultades,
    }, alertas


def verificar_vigencia_ccb(
    certificado: CertificadoExistencia | None,
    fecha_radicacion: date,
) -> tuple[dict, list[Alerta]]:
    """Antiguedad del certificado de existencia contra la fecha de radicacion."""
    alertas: list[Alerta] = []
    if certificado is None:
        alertas.append(
            Alerta(
                tipo=TipoAlerta.DOCUMENTO_FALTANTE,
                severidad=Severidad.CRITICA,
                mensaje="El Modulo 1 no aporta certificado de existencia y representacion legal",
                esperado=f"Certificado de Camara de Comercio con maximo {DIAS_VIGENCIA_CCB} dias",
                encontrado="No suministrado",
            )
        )
        return {"dias_antiguedad": Dato.ausente("Certificado de Camara de Comercio")}, alertas

    if not certificado.fecha_expedicion.presente:
        alertas.append(
            Alerta(
                tipo=TipoAlerta.DOCUMENTO_FALTANTE,
                severidad=Severidad.ALTA,
                mensaje=(
                    "El certificado de existencia no declara fecha de expedicion; "
                    "no es posible calcular su vigencia"
                ),
                esperado="Fecha de expedicion legible",
                encontrado="No suministrada",
                traza=certificado.fecha_expedicion.traza,
            )
        )
        return {
            "razon_social": certificado.razon_social,
            "nit": certificado.nit,
            "dias_antiguedad": Dato.ausente("Fecha de expedicion del certificado"),
        }, alertas

    expedicion = certificado.fecha_expedicion.exigir()
    dias = (fecha_radicacion - expedicion).days

    if dias > DIAS_VIGENCIA_CCB:
        alertas.append(
            Alerta(
                tipo=TipoAlerta.CCB_VENCIDA,
                severidad=Severidad.CRITICA,
                mensaje=(
                    f"El certificado de existencia tiene {dias} dias a la fecha de "
                    f"radicacion y excede el maximo de {DIAS_VIGENCIA_CCB}"
                ),
                esperado=f"Maximo {DIAS_VIGENCIA_CCB} dias calendario",
                encontrado=f"{dias} dias (expedido el {expedicion.isoformat()})",
                traza=certificado.fecha_expedicion.traza,
            )
        )
    elif dias < 0:
        alertas.append(
            Alerta(
                tipo=TipoAlerta.CCB_VENCIDA,
                severidad=Severidad.ALTA,
                mensaje=(
                    "El certificado de existencia declara fecha de expedicion "
                    "posterior a la radicacion del tramite"
                ),
                esperado=f"Expedicion anterior o igual a {fecha_radicacion.isoformat()}",
                encontrado=expedicion.isoformat(),
                traza=certificado.fecha_expedicion.traza,
            )
        )

    return {
        "razon_social": certificado.razon_social,
        "nit": certificado.nit,
        "representante_legal": certificado.representante_legal,
        "fecha_expedicion": certificado.fecha_expedicion,
        "dias_antiguedad": Dato.recomendado(
            dias,
            f"Diferencia entre radicacion ({fecha_radicacion.isoformat()}) y "
            f"expedicion ({expedicion.isoformat()})",
        ),
    }, alertas


def _rol_de(certificado: CertificadoBPM) -> str:
    if not certificado.rol_declarado.presente:
        return str(RolFabricante.INDETERMINADO)
    return certificado.rol_declarado.exigir()


def _esperado_para_rol(matriz: MatrizResponsabilidades, rol: str) -> Dato[str] | None:
    if rol == str(RolFabricante.SUSTANCIA_ACTIVA):
        return matriz.fabricante_sustancia_activa
    if rol == str(RolFabricante.PRODUCTO_TERMINADO):
        return matriz.fabricante_producto_terminado
    return None


def verificar_bpm(
    certificados: tuple[CertificadoBPM, ...],
    matriz: MatrizResponsabilidades | None,
    fecha_radicacion: date,
) -> tuple[tuple[dict, ...], list[Alerta]]:
    """Vigencia de los BPM y correspondencia con la matriz de responsabilidades.

    Los certificados y la matriz se tratan como dos fuentes independientes, igual
    que el A1 trata el check normativo del solicitante frente al Manual. Cuando
    discrepan no se escoge una: se muestran las dos.
    """
    alertas: list[Alerta] = []
    filas: list[dict] = []

    for certificado in certificados:
        rol = _rol_de(certificado)
        fila: dict = {
            "fabricante": certificado.fabricante,
            "pais": certificado.pais,
            "rol_declarado": certificado.rol_declarado,
            "fecha_emision": certificado.fecha_emision,
            "fecha_vencimiento": certificado.fecha_vencimiento,
        }

        if certificado.fecha_vencimiento.presente:
            vence = certificado.fecha_vencimiento.exigir()
            fila["vigente_a_la_radicacion"] = Dato.recomendado(
                vence >= fecha_radicacion,
                f"Vencimiento {vence.isoformat()} contra radicacion "
                f"{fecha_radicacion.isoformat()}",
            )
            if vence < fecha_radicacion:
                alertas.append(
                    Alerta(
                        tipo=TipoAlerta.BPM_VENCIDA,
                        severidad=Severidad.CRITICA,
                        mensaje=(
                            f"El certificado de BPM de "
                            f"{certificado.fabricante.valor or 'fabricante no identificado'} "
                            f"vencio antes de la radicacion"
                        ),
                        esperado=f"Vigente al {fecha_radicacion.isoformat()}",
                        encontrado=f"Vencio el {vence.isoformat()}",
                        traza=certificado.fecha_vencimiento.traza,
                    )
                )
        else:
            fila["vigente_a_la_radicacion"] = Dato.ausente(
                "Fecha de vencimiento del certificado de BPM"
            )
            alertas.append(
                Alerta(
                    tipo=TipoAlerta.BPM_VENCIDA,
                    severidad=Severidad.ALTA,
                    mensaje=(
                        f"El certificado de BPM de "
                        f"{certificado.fabricante.valor or 'fabricante no identificado'} "
                        f"no declara fecha de vencimiento"
                    ),
                    esperado="Fecha de vencimiento legible",
                    encontrado="No suministrada",
                    traza=certificado.fecha_vencimiento.traza,
                )
            )

        if rol == str(RolFabricante.INDETERMINADO):
            alertas.append(
                Alerta(
                    tipo=TipoAlerta.BPM_ROL_FALTANTE,
                    severidad=Severidad.ALTA,
                    mensaje=(
                        f"El certificado de BPM de "
                        f"{certificado.fabricante.valor or 'fabricante no identificado'} "
                        f"no declara el rol que ampara"
                    ),
                    esperado="Fabricante de Sustancia Activa o de Producto Terminado",
                    encontrado="Rol no declarado",
                    traza=certificado.rol_declarado.traza,
                )
            )

        if matriz is not None:
            esperado = _esperado_para_rol(matriz, rol)
            if esperado is not None and esperado.presente:
                declarado = esperado.exigir()
                certificado_nombre = certificado.fabricante.valor or ""
                coincide = coinciden_razon_social(certificado_nombre, declarado)
                fila["coincide_con_matriz"] = Dato.recomendado(
                    coincide,
                    f"Comparacion normalizada entre el certificado de BPM y la "
                    f"matriz de responsabilidades para el rol '{rol}'",
                )
                if not coincide:
                    alertas.append(
                        Alerta(
                            tipo=TipoAlerta.BPM_INCOHERENTE,
                            severidad=Severidad.CRITICA,
                            mensaje=(
                                f"El fabricante que ampara el BPM para el rol '{rol}' no "
                                f"corresponde al declarado en la matriz de responsabilidades"
                            ),
                            esperado=f"{declarado} (matriz de responsabilidades)",
                            encontrado=f"{certificado_nombre} (certificado de BPM)",
                            traza=certificado.fabricante.traza,
                        )
                    )

        filas.append(fila)

    if matriz is not None:
        roles_cubiertos = {_rol_de(c) for c in certificados}
        exigidos = (
            (RolFabricante.SUSTANCIA_ACTIVA, matriz.fabricante_sustancia_activa),
            (RolFabricante.PRODUCTO_TERMINADO, matriz.fabricante_producto_terminado),
        )
        for rol, declarado in exigidos:
            if declarado is not None and declarado.presente and str(rol) not in roles_cubiertos:
                alertas.append(
                    Alerta(
                        tipo=TipoAlerta.BPM_ROL_FALTANTE,
                        severidad=Severidad.CRITICA,
                        mensaje=(
                            f"La matriz declara un {rol} pero el Modulo 1 no aporta "
                            f"certificado de BPM que lo ampare"
                        ),
                        esperado=f"Certificado de BPM para {declarado.exigir()}",
                        encontrado="No suministrado",
                    )
                )

    return tuple(filas), alertas


def verificar_coherencia_nit(
    expediente: ExpedienteLegal,
) -> tuple[dict, list[Alerta]]:
    """El NIT del representante debe ser el mismo en poder, CCB y formulario."""
    alertas: list[Alerta] = []
    fuentes: dict[str, Dato[str] | None] = {
        "formulario_fm113": expediente.nit_formulario,
        "poder_especial": expediente.poder.nit_apoderado if expediente.poder else None,
        "certificado_camara_comercio": (
            expediente.certificado_existencia.nit
            if expediente.certificado_existencia
            else None
        ),
    }

    presentes = {
        nombre: dato.exigir()
        for nombre, dato in fuentes.items()
        if dato is not None and dato.presente
    }

    salida: dict = {nombre: (dato or Dato.ausente(f"NIT en {nombre}")) for nombre, dato in fuentes.items()}

    if len(presentes) < 2:
        salida["coincidencia"] = Dato.ausente(
            "NIT en al menos dos documentos para poder cruzarlos"
        )
        return salida, alertas

    referencia_nombre, referencia = next(iter(presentes.items()))
    discrepantes = {
        nombre: valor
        for nombre, valor in presentes.items()
        if not coinciden_nit(referencia, valor)
    }

    salida["coincidencia"] = Dato.recomendado(
        not discrepantes,
        "Cruce del NIT normalizado entre " + ", ".join(presentes),
    )

    if discrepantes:
        alertas.append(
            Alerta(
                tipo=TipoAlerta.NIT_INCOHERENTE,
                severidad=Severidad.CRITICA,
                mensaje=(
                    "El NIT del representante legal no es el mismo en todos los "
                    "documentos del Modulo 1"
                ),
                esperado=f"{referencia} (segun {referencia_nombre})",
                encontrado="; ".join(f"{n}: {v}" for n, v in discrepantes.items()),
            )
        )

    return salida, alertas


def validar_modulo1(
    expediente: ExpedienteLegal,
    fecha_radicacion: date,
) -> VerificacionLegal:
    """Corre las cuatro verificaciones y consolida las alertas."""
    alertas: list[Alerta] = []

    poder, a_poder = verificar_poder(expediente.poder)
    alertas.extend(a_poder)

    ccb, a_ccb = verificar_vigencia_ccb(
        expediente.certificado_existencia, fecha_radicacion
    )
    alertas.extend(a_ccb)

    bpm, a_bpm = verificar_bpm(
        expediente.certificados_bpm, expediente.matriz, fecha_radicacion
    )
    alertas.extend(a_bpm)

    nit, a_nit = verificar_coherencia_nit(expediente)
    alertas.extend(a_nit)

    return VerificacionLegal(
        poder=poder,
        certificado_existencia=ccb,
        bpm=bpm,
        coherencia_nit=nit,
        alertas=ordenar(tuple(alertas)),
    )
