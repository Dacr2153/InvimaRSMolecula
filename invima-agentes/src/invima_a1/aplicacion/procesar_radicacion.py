"""Caso de uso del agente A1-RCE.

Maquina de estados explicita de nueve pasos. Cada paso emite un evento de
auditoria y consulta el dominio para decidir si continua.

El paso 9 es terminal para el agente: deja el expediente en
PENDIENTE_VALIDACION_HUMANA y no existe metodo aqui que lo saque de ahi. Sacarlo
requiere `registrar_decision_humana`, que vive en supervision.py y exige el
nombre del servidor publico responsable.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from ..domain.auditoria import EventoAuditoria, TipoEvento
from ..domain.estados import EstadoExpediente
from ..domain.modelos import (
    AprobacionAgencia,
    ContenidoSospechoso,
    Expediente,
    Pago,
)
from ..domain.servicios import sanitizador
from ..domain.servicios.contrastador_indicaciones import (
    ReporteCoincidenciaInternacional,
    contrastar_indicaciones,
)
from ..domain.servicios.enrutador import Enrutamiento, recomendar_ruta
from ..domain.servicios.motor_normativo import (
    ResultadoEvaluacionNormativa,
    evaluar_normas,
)
from ..domain.servicios.validador_transaccional import (
    ResultadoValidacionPago,
    validar_pago,
)
from ..domain.valores import Dato, Dinero, Traza
from ..puertos import (
    AgenciaReferenciaPort,
    AuditLogPort,
    DocumentoParserPort,
    EnsayosClinicosPort,
    ExtractorMetadatosPort,
    NormasFarmacologicasPort,
    RepositorioExpedientePort,
    TarifarioPort,
    TransaccionesPort,
)
from .dto import DatosRadicacion, construir_payload
from .esquemas import (
    ESQUEMA_AUTOVALIDACION,
    ESQUEMA_FM113,
    INSTRUCCION_AUTOVALIDACION,
    INSTRUCCION_FM113,
)

FORMULARIO = "ASS-RSA-FM113"


@dataclass(frozen=True, slots=True)
class Dependencias:
    parser: DocumentoParserPort
    extractor: ExtractorMetadatosPort
    tarifario: TarifarioPort
    transacciones: TransaccionesPort
    agencias: Sequence[AgenciaReferenciaPort]
    ensayos: EnsayosClinicosPort
    normas: NormasFarmacologicasPort
    repositorio: RepositorioExpedientePort
    auditoria: AuditLogPort
    reloj: Callable[[], datetime]


@dataclass(frozen=True, slots=True)
class ResultadoProcesamiento:
    expediente: Expediente
    payload: dict[str, Any]

    @property
    def suspendido(self) -> bool:
        return self.expediente.estado is EstadoExpediente.SUSPENDIDO_POR_INCONSISTENCIA


def _traza_doc(pagina: int | None, seccion: str, campo: str) -> Traza:
    return Traza.en_documento(
        modulo="Modulo 1",
        seccion=f"{FORMULARIO} > {seccion}",
        pagina=pagina,
        campo=campo,
    )


def _dato_texto(
    bloque: dict[str, Any], clave: str, seccion: str, etiqueta: str
) -> Dato[str]:
    valor = bloque.get(clave)
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return Dato.ausente(f"{seccion} > {etiqueta}")
    return Dato.extraido(str(valor).strip(), _traza_doc(bloque.get("pagina"), seccion, etiqueta))


def _dato_dinero(bloque: dict[str, Any], clave: str, seccion: str) -> Dato[Dinero]:
    valor = bloque.get(clave)
    if valor is None:
        return Dato.ausente(f"{seccion} > Valor pagado")
    try:
        monto = Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return Dato.ausente(f"{seccion} > Valor pagado (formato no interpretable)")
    return Dato.extraido(
        Dinero(monto), _traza_doc(bloque.get("pagina"), seccion, "Valor pagado")
    )


def _fecha(texto: str | None) -> date | None:
    if not texto:
        return None
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(texto.strip(), formato).date()
        except ValueError:
            continue
    return None


class ProcesarRadicacionUseCase:
    """Orquestador del agente A1-RCE."""

    def __init__(self, deps: Dependencias) -> None:
        self._d = deps
        self._sospechosos: list[ContenidoSospechoso] = []

    def ejecutar(
        self,
        carpeta_dossier: Path,
        radicado: str,
        patron_folios: str = "*",
    ) -> ResultadoProcesamiento:
        """Procesa el expediente.

        `patron_folios` acota que folios entran al agente. El A1 solo necesita el
        Modulo 1; pasarle el Modulo 3 completo son decenas de paginas de tokens
        que no usa. Los demas modulos son insumo de los otros agentes.
        """
        d = self._d
        self._sospechosos = []
        expediente = Expediente(radicado=radicado, fecha_radicacion=d.reloj().date())

        # Paso 1 - Ingesta
        documentos = self._ingestar(expediente, carpeta_dossier, patron_folios)

        # Paso 2 - Extraccion de metadatos del formulario
        crudo_fm113 = self._extraer(
            expediente,
            "Extraccion de metadatos ASS-RSA-FM113",
            documentos,
            ESQUEMA_FM113,
            INSTRUCCION_FM113,
        )
        expediente.avanzar_a(EstadoExpediente.METADATOS_EXTRAIDOS, d.reloj())
        datos, pago = self._mapear_fm113(crudo_fm113)

        # Paso 3 - Validacion transaccional. Corta el flujo si el pago no cuadra.
        validacion = self._validar_pago(expediente, pago)
        if not validacion.conforme:
            return self._suspender(expediente, datos, validacion)
        expediente.avanzar_a(EstadoExpediente.PAGO_VALIDADO, d.reloj())

        # Paso 4 - Autovalidacion farmaceutica declarada por el solicitante
        crudo_auto = self._extraer(
            expediente,
            "Extraccion de autovalidacion farmaceutica",
            documentos,
            ESQUEMA_AUTOVALIDACION,
            INSTRUCCION_AUTOVALIDACION,
        )
        datos = self._mapear_certificado(datos, crudo_auto)

        # Paso 5 - Reliance: verificacion contra fuentes publicas
        aprobaciones = self._buscar_reliance(expediente, datos, crudo_auto)

        # Paso 6 - Contraste de indicaciones
        reporte = self._contrastar(expediente, datos, aprobaciones)
        expediente.avanzar_a(EstadoExpediente.RELIANCE_COMPLETADO, d.reloj())

        # Paso 7 - Bypass check contra el Manual de Normas Farmacologicas
        evaluacion = self._evaluar_normas(expediente, datos, crudo_auto)
        expediente.avanzar_a(EstadoExpediente.NORMAS_EVALUADAS, d.reloj())

        # Paso 8 - Recomendacion de ruta
        enrutamiento = self._enrutar(expediente, evaluacion)
        expediente.avanzar_a(EstadoExpediente.RUTA_RECOMENDADA, d.reloj())

        # Paso 9 - Entrega al evaluador. Fin del agente.
        return self._presentar(
            expediente, datos, validacion, reporte, evaluacion, enrutamiento
        )

    # ------------------------------------------------------------------ pasos

    def _ingestar(
        self, expediente: Expediente, carpeta: Path, patron: str = "*"
    ) -> str:
        d = self._d
        self._log(expediente, TipoEvento.PASO_INICIADO, "Ingesta del Modulo 1", "")

        if carpeta.is_dir():
            archivos = sorted(carpeta.glob(f"{patron}.pdf")) or sorted(
                carpeta.glob(f"{patron}.md")
            )
        else:
            archivos = [carpeta]
        if not archivos:
            raise FileNotFoundError(f"No hay documentos procesables en {carpeta}")

        partes: list[str] = []
        for archivo in archivos:
            parseado = d.parser.parsear(archivo)
            partes.append(f"### Documento: {parseado.nombre_archivo}\n{parseado.markdown}")
            self._log(
                expediente,
                TipoEvento.PASO_COMPLETADO,
                f"Ingesta de {parseado.nombre_archivo}",
                f"{parseado.paginas} paginas, {len(parseado.secciones)} secciones",
            )

        expediente.avanzar_a(EstadoExpediente.INGESTADO, d.reloj())
        return "\n\n".join(partes)

    def _extraer(
        self,
        expediente: Expediente,
        accion: str,
        contenido: str,
        esquema: dict[str, Any],
        instruccion: str,
    ) -> dict[str, Any]:
        d = self._d
        self._log(expediente, TipoEvento.PASO_INICIADO, accion, "")
        crudo = d.extractor.extraer(contenido, esquema, instruccion)
        self._log(
            expediente,
            TipoEvento.LLAMADA_MODELO,
            accion,
            f"Extraccion completada con {d.extractor.identificador_modelo}",
            detalles={"modelo": d.extractor.identificador_modelo},
        )
        self._revisar_inyeccion(expediente, crudo)
        return crudo

    def _validar_pago(
        self, expediente: Expediente, pago: Pago
    ) -> ResultadoValidacionPago:
        d = self._d
        self._log(expediente, TipoEvento.PASO_INICIADO, "Validacion transaccional", "")

        codigo = pago.codigo_tarifa.valor
        comprobante = pago.comprobante_numero.valor
        tarifa = d.tarifario.buscar(codigo) if codigo else None
        transaccion = d.transacciones.buscar(comprobante) if comprobante else None

        resultado = validar_pago(pago, tarifa, transaccion)
        self._log(
            expediente,
            TipoEvento.PASO_COMPLETADO if resultado.conforme else TipoEvento.ALERTA,
            "Validacion transaccional",
            resultado.resumen,
        )
        return resultado

    def _buscar_reliance(
        self,
        expediente: Expediente,
        datos: DatosRadicacion,
        crudo_auto: dict[str, Any],
    ) -> tuple[AprobacionAgencia, ...]:
        d = self._d
        principio = datos.producto["principio_activo"].valor
        aprobaciones: list[AprobacionAgencia] = []

        declaradas: dict[str, dict[str, Any]] = {}
        for item in crudo_auto.get("aprobaciones_declaradas") or []:
            agencia = str(item.get("agencia", "")).strip().upper()
            if agencia:
                declaradas[agencia] = item

        if principio:
            for puerto in d.agencias:
                respuesta = puerto.consultar(principio)
                self._log(
                    expediente,
                    TipoEvento.CONSULTA_EXTERNA,
                    f"Consulta a {puerto.nombre}",
                    "Encontrada" if respuesta.encontrada else "Sin coincidencia",
                    detalles={"url": respuesta.url_fuente},
                )
                if not respuesta.encontrada:
                    continue
                traza = Traza.en_fuente_publica(puerto.nombre, respuesta.url_fuente)
                aprobaciones.append(
                    AprobacionAgencia(
                        agencia=puerto.nombre,
                        fecha_aprobacion=(
                            Dato.de_busqueda(respuesta.fecha_aprobacion, traza)
                            if respuesta.fecha_aprobacion
                            else Dato.ausente(f"Fecha de aprobacion en {puerto.nombre}")
                        ),
                        indicacion_aprobada=(
                            Dato.de_busqueda(respuesta.indicacion_aprobada, traza)
                            if respuesta.indicacion_aprobada
                            else Dato.ausente(f"Indicacion aprobada en {puerto.nombre}")
                        ),
                        declarada_por_solicitante=puerto.nombre.upper() in declaradas,
                        verificada_en_fuente=True,
                    )
                )

        verificadas = {a.agencia.upper() for a in aprobaciones}
        for agencia, item in declaradas.items():
            if agencia in verificadas:
                continue
            traza = _traza_doc(
                item.get("pagina"), "Matriz de autovalidacion", f"Aprobacion {agencia}"
            )
            fecha = _fecha(item.get("fecha_aprobacion"))
            aprobaciones.append(
                AprobacionAgencia(
                    agencia=agencia,
                    fecha_aprobacion=(
                        Dato.extraido(fecha, traza)
                        if fecha
                        else Dato.ausente(f"Fecha declarada para {agencia}")
                    ),
                    indicacion_aprobada=(
                        Dato.extraido(str(item["indicacion_aprobada"]), traza)
                        if item.get("indicacion_aprobada")
                        else Dato.ausente(f"Indicacion declarada para {agencia}")
                    ),
                    declarada_por_solicitante=True,
                    verificada_en_fuente=False,
                )
            )

        for nct in crudo_auto.get("nct_ids_declarados") or []:
            respuesta = d.ensayos.consultar(str(nct))
            self._log(
                expediente,
                TipoEvento.CONSULTA_EXTERNA,
                f"Verificacion de ensayo clinico {nct}",
                (
                    f"{respuesta.estatus} (resultados disponibles: "
                    f"{respuesta.resultados_disponibles})"
                    if respuesta.encontrado
                    else "No encontrado en el registro publico"
                ),
                detalles={"url": respuesta.url_fuente},
            )

        return tuple(aprobaciones)

    def _contrastar(
        self,
        expediente: Expediente,
        datos: DatosRadicacion,
        aprobaciones: tuple[AprobacionAgencia, ...],
    ) -> ReporteCoincidenciaInternacional:
        reporte = contrastar_indicaciones(
            molecula=datos.producto["principio_activo"].valor or "No suministrado",
            indicacion_solicitada=datos.producto["indicacion_solicitada"].valor,
            aprobaciones=aprobaciones,
        )
        if reporte.hay_indicacion_mas_amplia:
            self._log(
                expediente,
                TipoEvento.ALERTA,
                "Contraste de indicaciones",
                "La indicacion solicitada excede el alcance aprobado por al menos "
                "una agencia de referencia",
            )
        else:
            self._log(
                expediente,
                TipoEvento.PASO_COMPLETADO,
                "Contraste de indicaciones",
                f"{len(reporte.contrastes)} agencias contrastadas",
            )
        return reporte

    def _evaluar_normas(
        self,
        expediente: Expediente,
        datos: DatosRadicacion,
        crudo_auto: dict[str, Any],
    ) -> ResultadoEvaluacionNormativa:
        d = self._d
        principio = datos.producto["principio_activo"]
        check = crudo_auto.get("check_molecula_no_incluida_en_normas")
        dato_check = (
            Dato.extraido(
                bool(check),
                _traza_doc(None, "Seccion normativa", "Check molecula no incluida"),
            )
            if check is not None
            else Dato.ausente("Check declarativo de inclusion en normas")
        )

        coincidencias = (
            d.normas.buscar(principio.exigir()) if principio.presente else ()
        )
        resultado = evaluar_normas(
            principio_activo=principio,
            check_no_incluida=dato_check,
            coincidencias_manual=coincidencias,
            version_manual=d.normas.version,
        )
        if resultado.discrepancia:
            self._log(
                expediente,
                TipoEvento.ALERTA,
                "Bypass check",
                resultado.discrepancia.mensaje,
            )
        else:
            self._log(
                expediente,
                TipoEvento.PASO_COMPLETADO,
                "Bypass check",
                str(resultado.estatus.valor),
            )
        return resultado

    def _enrutar(
        self, expediente: Expediente, evaluacion: ResultadoEvaluacionNormativa
    ) -> Enrutamiento:
        enrutamiento = recomendar_ruta(
            estatus=evaluacion.estatus.valor or "INDETERMINADA", pago_conforme=True
        )
        self._log(
            expediente,
            TipoEvento.PASO_COMPLETADO,
            "Recomendacion de enrutamiento",
            f"{enrutamiento.ruta.valor} hacia {enrutamiento.destino_primario.valor}",
        )
        return enrutamiento

    def _presentar(
        self,
        expediente: Expediente,
        datos: DatosRadicacion,
        validacion: ResultadoValidacionPago,
        reporte: ReporteCoincidenciaInternacional | None,
        evaluacion: ResultadoEvaluacionNormativa | None,
        enrutamiento: Enrutamiento | None,
    ) -> ResultadoProcesamiento:
        d = self._d
        expediente.avanzar_a(
            EstadoExpediente.PENDIENTE_VALIDACION_HUMANA,
            d.reloj(),
            detalle="Expediente a la espera de validacion por servidor publico competente",
        )
        payload = construir_payload(
            expediente=expediente,
            datos=datos,
            validacion_pago=validacion,
            reporte_internacional=reporte,
            evaluacion_normativa=evaluacion,
            enrutamiento=enrutamiento,
            contenido_sospechoso=tuple(self._sospechosos),
            modelo_usado=d.extractor.identificador_modelo,
        )
        d.repositorio.guardar(expediente, payload)
        return ResultadoProcesamiento(expediente=expediente, payload=payload)

    def _suspender(
        self,
        expediente: Expediente,
        datos: DatosRadicacion,
        validacion: ResultadoValidacionPago,
    ) -> ResultadoProcesamiento:
        d = self._d
        expediente.avanzar_a(
            EstadoExpediente.SUSPENDIDO_POR_INCONSISTENCIA,
            d.reloj(),
            detalle=validacion.resumen,
        )
        enrutamiento = recomendar_ruta(
            estatus="INDETERMINADA",
            pago_conforme=False,
            motivo_suspension=validacion.resumen,
        )
        payload = construir_payload(
            expediente=expediente,
            datos=datos,
            validacion_pago=validacion,
            reporte_internacional=None,
            evaluacion_normativa=None,
            enrutamiento=enrutamiento,
            contenido_sospechoso=tuple(self._sospechosos),
            modelo_usado=d.extractor.identificador_modelo,
        )
        d.repositorio.guardar(expediente, payload)
        return ResultadoProcesamiento(expediente=expediente, payload=payload)

    # ------------------------------------------------------------------ apoyo

    def _mapear_fm113(self, crudo: dict[str, Any]) -> tuple[DatosRadicacion, Pago]:
        sol = crudo.get("solicitante") or {}
        pro = crudo.get("producto") or {}
        tra = crudo.get("tramite") or {}
        pag = crudo.get("pago") or {}

        datos = DatosRadicacion(
            solicitante={
                "nombre_titular": _dato_texto(sol, "nombre_titular", "Solicitante", "Razon social"),
                "representante_colombia": _dato_texto(
                    sol, "representante_colombia", "Solicitante", "Representante en Colombia"
                ),
                "nit_representante": _dato_texto(
                    sol, "nit_representante", "Solicitante", "NIT"
                ),
            },
            producto={
                "nombre": _dato_texto(pro, "nombre", "Producto", "Nombre"),
                "principio_activo": _dato_texto(
                    pro, "principio_activo", "Producto", "Principio activo"
                ),
                "concentracion": _dato_texto(pro, "concentracion", "Producto", "Concentracion"),
                "forma_farmaceutica": _dato_texto(
                    pro, "forma_farmaceutica", "Producto", "Forma farmaceutica"
                ),
                "indicacion_solicitada": _dato_texto(
                    pro, "indicacion_solicitada", "Producto", "Indicacion solicitada"
                ),
            },
            tramite={
                "tipo_tramite": _dato_texto(tra, "tipo_tramite", "Tramite", "Tipo de tramite"),
                "modalidad": _dato_texto(tra, "modalidad", "Tramite", "Modalidad"),
                "ruta_estudio": _dato_texto(tra, "ruta_estudio", "Tramite", "Ruta de estudio"),
            },
            pago={
                "comprobante_numero": _dato_texto(
                    pag, "comprobante_numero", "Datos de pago", "Comprobante"
                ),
                "codigo_tarifa": _dato_texto(
                    pag, "codigo_tarifa", "Datos de pago", "Codigo de tarifa"
                ),
                "valor_pagado": _dato_dinero(pag, "valor_pagado", "Datos de pago"),
            },
            certificado={},
        )
        pago = Pago(
            comprobante_numero=datos.pago["comprobante_numero"],
            codigo_tarifa=datos.pago["codigo_tarifa"],
            valor_pagado=datos.pago["valor_pagado"],
        )
        return datos, pago

    def _mapear_certificado(
        self, datos: DatosRadicacion, crudo_auto: dict[str, Any]
    ) -> DatosRadicacion:
        cert = crudo_auto.get("certificado") or {}
        return DatosRadicacion(
            solicitante=datos.solicitante,
            producto=datos.producto,
            tramite=datos.tramite,
            pago=datos.pago,
            certificado={
                "tipo": _dato_texto(cert, "tipo", "Documentos de validacion", "Tipo"),
                "numero": _dato_texto(cert, "numero", "Documentos de validacion", "Numero"),
                "pais_emisor": _dato_texto(
                    cert, "pais_emisor", "Documentos de validacion", "Pais emisor"
                ),
                "autoridad_emisora": _dato_texto(
                    cert, "autoridad_emisora", "Documentos de validacion", "Autoridad emisora"
                ),
            },
        )

    def _revisar_inyeccion(self, expediente: Expediente, crudo: dict[str, Any]) -> None:
        campos: dict[str, str | None] = {}

        def recorrer(prefijo: str, nodo: Any) -> None:
            if isinstance(nodo, dict):
                for clave, valor in nodo.items():
                    recorrer(f"{prefijo}.{clave}" if prefijo else str(clave), valor)
            elif isinstance(nodo, list):
                for indice, valor in enumerate(nodo):
                    recorrer(f"{prefijo}[{indice}]", valor)
            elif isinstance(nodo, str):
                campos[prefijo] = nodo

        recorrer("", crudo)
        hallazgos = sanitizador.revisar_campos(campos)
        for hallazgo in hallazgos:
            self._sospechosos.append(hallazgo)
            self._log(
                expediente,
                TipoEvento.ALERTA,
                "Contenido sospechoso en el expediente",
                f"{hallazgo.motivo} (campo {hallazgo.campo})",
                detalles={"fragmento": hallazgo.fragmento},
            )

    def _log(
        self,
        expediente: Expediente,
        tipo: TipoEvento,
        accion: str,
        resultado: str,
        detalles: dict[str, Any] | None = None,
    ) -> None:
        evento = EventoAuditoria(
            momento=self._d.reloj(),
            tipo=tipo,
            radicado=expediente.radicado,
            accion=accion,
            resultado=resultado,
            detalles=detalles or {},
        )
        expediente.registrar(evento)
        self._d.auditoria.registrar(evento)
