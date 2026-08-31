"""Caso de uso del A2-VICR: validar el Modulo 1 y clasificar el producto.

Seis pasos, cada uno emitiendo auditoria bajo el mismo radicado que uso el A1.
El expediente queda reconstruible leyendo un solo log.

La coordinacion con el A1 se sostiene en tres reglas:

  1. El A2 consume el payload del A1; no vuelve a parsear ni a extraer el FM113.
  2. Si el A1 suspendio por inconsistencia de pago, el A2 no corre. El corte
     temprano del A1 se respeta aguas abajo en vez de reabrirse: extraer
     documentos legales de un tramite que no puede repartirse es gasto sin destino.
  3. El estatus normativo y la ruta EXPRESS/ESTANDAR no se recalculan. Se
     heredan del A1 y se muestran junto a los hallazgos legales.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Callable

from invima_a1.domain.auditoria import EventoAuditoria, TipoEvento
from invima_a1.domain.modelos import ContenidoSospechoso
from invima_a1.domain.servicios import sanitizador

from ..domain.errores import ExpedienteNoValidableError
from ..domain.estados import EstadoDictamen
from ..domain.modelos import (
    CertificadoBPM,
    CertificadoExistencia,
    Dictamen,
    ExpedienteLegal,
    MatrizResponsabilidades,
    PerfilProducto,
    PoderEspecial,
)
from ..domain.servicios.clasificador_producto import clasificar
from ..domain.servicios.motor_alertas import (
    Alerta,
    Severidad,
    TipoAlerta,
    hay_bloqueo,
    ordenar,
)
from ..domain.servicios.validador_legal import validar_modulo1
from ..domain.valores import Dato, Traza
from ..puertos import AuditLogPort, DocumentoParserPort, ExpedienteA1Port, ExtractorMetadatosPort
from .dto import construir_payload
from .esquemas import ESQUEMA_LEGAL, INSTRUCCION_LEGAL

#: Estado en que el A1 entrega un expediente apto para la etapa siguiente.
ESTADOS_A1_VALIDABLES = frozenset({"PENDIENTE_VALIDACION_HUMANA", "ENRUTADO"})

_SECCION = "Documentos legales del Modulo 1"


@dataclass(frozen=True, slots=True)
class Dependencias:
    expediente_a1: ExpedienteA1Port
    parser: DocumentoParserPort
    extractor: ExtractorMetadatosPort
    auditoria: AuditLogPort
    reloj: Callable[[], datetime] = lambda: datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class ResultadoDictamen:
    dictamen: Dictamen
    payload: dict[str, Any]

    @property
    def retenido(self) -> bool:
        return self.dictamen.estado is EstadoDictamen.RETENIDO_POR_ALERTA_CRITICA


def _traza(campo: str, pagina: int | None = None) -> Traza:
    return Traza.en_documento("Modulo 1", _SECCION, pagina, campo)


def _texto(bloque: dict[str, Any], clave: str, pagina: int | None) -> Dato[str]:
    valor = bloque.get(clave)
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return Dato.ausente(f"{clave} en {_SECCION}")
    return Dato.extraido(str(valor).strip(), _traza(clave, pagina))


def _booleano(bloque: dict[str, Any], clave: str, pagina: int | None) -> Dato[bool]:
    valor = bloque.get(clave)
    if valor is None:
        return Dato.ausente(f"{clave} en {_SECCION}")
    return Dato.extraido(bool(valor), _traza(clave, pagina))


def _fecha(bloque: dict[str, Any], clave: str, pagina: int | None) -> Dato[date]:
    crudo = bloque.get(clave)
    if not crudo:
        return Dato.ausente(f"{clave} en {_SECCION}")
    try:
        return Dato.extraido(date.fromisoformat(str(crudo).strip()), _traza(clave, pagina))
    except ValueError:
        # Una fecha ilegible no se adivina. Se reporta como no suministrada y la
        # regla que dependia de ella levanta su propia alerta.
        return Dato.ausente(f"{clave} en {_SECCION} (formato no reconocido: {crudo})")


class ValidarYClasificarUseCase:
    """Agente A2-VICR."""

    def __init__(self, deps: Dependencias) -> None:
        self._d = deps
        self._sospechosos: list[ContenidoSospechoso] = []

    def ejecutar(self, radicado: str) -> ResultadoDictamen:
        d = self._d
        self._sospechosos = []

        # Paso 1 - Recepcion del payload del A1
        payload_a1 = self._recibir(radicado)
        fecha_radicacion = self._fecha_radicacion(payload_a1)
        dictamen = Dictamen(radicado=radicado, fecha_radicacion=fecha_radicacion)

        # Paso 2 - Lectura y extraccion de los documentos legales del Modulo 1
        crudo = self._extraer(dictamen, radicado)

        # Paso 3 - Validacion legal del Modulo 1
        expediente = self._mapear_legal(crudo, payload_a1)
        verificacion = validar_modulo1(expediente, fecha_radicacion)
        self._log(
            dictamen,
            TipoEvento.PASO_COMPLETADO if not verificacion.alertas else TipoEvento.ALERTA,
            "Validacion legal del Modulo 1",
            f"{len(verificacion.alertas)} hallazgo(s)",
        )
        dictamen.avanzar_a(EstadoDictamen.LEGAL_VALIDADO)

        # Paso 4 - Clasificacion taxonomica del producto
        clasificacion = clasificar(self._mapear_perfil(crudo, payload_a1))
        self._log(
            dictamen,
            TipoEvento.PASO_COMPLETADO,
            "Clasificacion taxonomica",
            f"{clasificacion.dimension.valor} / {clasificacion.ruta_estudio.valor}",
        )
        dictamen.avanzar_a(EstadoDictamen.CLASIFICADO)

        # Paso 5 - Consolidacion de alertas
        alertas = self._consolidar(verificacion.alertas, clasificacion.alertas)

        # Paso 6 - Entrega al Coordinador de Grupos. Fin del agente.
        destino = (
            EstadoDictamen.RETENIDO_POR_ALERTA_CRITICA
            if hay_bloqueo(alertas)
            else EstadoDictamen.PENDIENTE_VALIDACION_COORDINADOR
        )
        dictamen.avanzar_a(destino)
        self._log(
            dictamen,
            TipoEvento.CAMBIO_ESTADO,
            "Entrega del dictamen",
            str(destino),
        )

        payload = construir_payload(
            radicado=radicado,
            estado=str(dictamen.estado),
            verificacion=verificacion,
            clasificacion=clasificacion,
            alertas=alertas,
            estatus_normas_a1=payload_a1.get("evaluacion_normativa"),
            enrutamiento_a1=payload_a1.get("enrutamiento"),
            sospechosos=tuple(self._sospechosos),
            modelo_usado=d.extractor.identificador_modelo,
        )
        return ResultadoDictamen(dictamen=dictamen, payload=payload)

    # ------------------------------------------------------------------ pasos

    def _recibir(self, radicado: str) -> dict[str, Any]:
        payload = self._d.expediente_a1.cargar(radicado)
        estado = (payload.get("radicacion") or {}).get("estado")

        if estado not in ESTADOS_A1_VALIDABLES:
            raise ExpedienteNoValidableError(
                f"El A1 dejo el radicado {radicado} en estado {estado}. El A2 solo "
                f"valida expedientes entregados al evaluador ({', '.join(sorted(ESTADOS_A1_VALIDABLES))}). "
                f"Un tramite suspendido por inconsistencia de pago no se reparte, "
                f"asi que extraer sus documentos legales seria gasto sin destino."
            )
        return payload

    def _fecha_radicacion(self, payload: dict[str, Any]) -> date:
        crudo = (payload.get("radicacion") or {}).get("fecha_radicacion")
        if not crudo:
            raise ExpedienteNoValidableError(
                "El payload del A1 no declara fecha de radicacion; sin ella no se "
                "puede calcular la vigencia del certificado de existencia."
            )
        return date.fromisoformat(str(crudo))

    def _extraer(self, dictamen: Dictamen, radicado: str) -> dict[str, Any]:
        d = self._d
        self._log(dictamen, TipoEvento.PASO_INICIADO, "Lectura de documentos legales", "")

        carpeta = d.expediente_a1.carpeta_dossier(radicado)
        if carpeta.is_dir():
            archivos = sorted(carpeta.glob("*.pdf")) or sorted(carpeta.glob("*.md"))
        else:
            archivos = [carpeta]
        if not archivos:
            raise FileNotFoundError(f"No hay documentos procesables en {carpeta}")

        partes: list[str] = []
        for archivo in archivos:
            parseado = d.parser.parsear(archivo)
            partes.append(f"### Documento: {parseado.nombre_archivo}\n{parseado.markdown}")
        contenido = "\n\n".join(partes)

        crudo = d.extractor.extraer(contenido, ESQUEMA_LEGAL, INSTRUCCION_LEGAL)
        self._log(
            dictamen,
            TipoEvento.LLAMADA_MODELO,
            "Extraccion de documentos legales",
            f"Extraccion completada con {d.extractor.identificador_modelo}",
            detalles={"modelo": d.extractor.identificador_modelo},
        )
        self._revisar_inyeccion(dictamen, crudo)
        return crudo

    def _revisar_inyeccion(self, dictamen: Dictamen, crudo: dict[str, Any]) -> None:
        """Los documentos legales los redacta el mismo tercero interesado.

        Un poder o un certificado traducido es texto libre que llega al modelo, y
        por tanto superficie de inyeccion igual que las observaciones del FM113.
        """
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
        for hallazgo in sanitizador.revisar_campos(campos):
            self._sospechosos.append(hallazgo)
            self._log(
                dictamen,
                TipoEvento.ALERTA,
                "Contenido sospechoso en documentos legales",
                f"{hallazgo.motivo} (campo {hallazgo.campo})",
                detalles={"fragmento": hallazgo.fragmento},
            )

    def _consolidar(
        self, legales: tuple[Alerta, ...], taxonomicas: tuple[Alerta, ...]
    ) -> tuple[Alerta, ...]:
        alertas = list(legales) + list(taxonomicas)
        for hallazgo in self._sospechosos:
            alertas.append(
                Alerta(
                    tipo=TipoAlerta.CONTENIDO_SOSPECHOSO,
                    severidad=Severidad.ALTA,
                    mensaje=(
                        "Un documento legal del Modulo 1 contiene texto que aparenta "
                        "dar instrucciones al sistema"
                    ),
                    esperado="Texto documental",
                    encontrado=f"{hallazgo.motivo} en {hallazgo.campo}",
                    traza=hallazgo.traza,
                )
            )
        return ordenar(tuple(alertas))

    # ------------------------------------------------------------------ mapeo

    def _mapear_legal(
        self, crudo: dict[str, Any], payload_a1: dict[str, Any]
    ) -> ExpedienteLegal:
        poder_crudo = crudo.get("poder_especial") or {}
        ccb_crudo = crudo.get("certificado_existencia") or {}
        matriz_crudo = crudo.get("matriz_responsabilidades") or {}

        poder = None
        if any(v is not None for k, v in poder_crudo.items() if k != "pagina"):
            pagina = poder_crudo.get("pagina")
            poder = PoderEspecial(
                otorgante=_texto(poder_crudo, "otorgante", pagina),
                apoderado=_texto(poder_crudo, "apoderado", pagina),
                nit_apoderado=_texto(poder_crudo, "nit_apoderado", pagina),
                apostilla_presente=_booleano(poder_crudo, "apostilla_presente", pagina),
                autoridad_apostilla=_texto(poder_crudo, "autoridad_apostilla", pagina),
                traductor_oficial=_texto(poder_crudo, "traductor_oficial", pagina),
                facultades=_texto(poder_crudo, "facultades", pagina),
            )

        ccb = None
        if any(v is not None for k, v in ccb_crudo.items() if k != "pagina"):
            pagina = ccb_crudo.get("pagina")
            ccb = CertificadoExistencia(
                razon_social=_texto(ccb_crudo, "razon_social", pagina),
                nit=_texto(ccb_crudo, "nit", pagina),
                representante_legal=_texto(ccb_crudo, "representante_legal", pagina),
                fecha_expedicion=_fecha(ccb_crudo, "fecha_expedicion", pagina),
                camara=_texto(ccb_crudo, "camara", pagina),
            )

        bpm: list[CertificadoBPM] = []
        for fila in crudo.get("certificados_bpm") or []:
            pagina = fila.get("pagina")
            bpm.append(
                CertificadoBPM(
                    fabricante=_texto(fila, "fabricante", pagina),
                    pais=_texto(fila, "pais", pagina),
                    rol_declarado=_texto(fila, "rol_declarado", pagina),
                    fecha_emision=_fecha(fila, "fecha_emision", pagina),
                    fecha_vencimiento=_fecha(fila, "fecha_vencimiento", pagina),
                    autoridad_emisora=_texto(fila, "autoridad_emisora", pagina),
                )
            )

        matriz = None
        if any(v is not None for k, v in matriz_crudo.items() if k != "pagina"):
            pagina = matriz_crudo.get("pagina")
            matriz = MatrizResponsabilidades(
                titular=_texto(matriz_crudo, "titular", pagina),
                fabricante_sustancia_activa=_texto(
                    matriz_crudo, "fabricante_sustancia_activa", pagina
                ),
                fabricante_producto_terminado=_texto(
                    matriz_crudo, "fabricante_producto_terminado", pagina
                ),
                importador=_texto(matriz_crudo, "importador", pagina),
            )

        return ExpedienteLegal(
            poder=poder,
            certificado_existencia=ccb,
            certificados_bpm=tuple(bpm),
            matriz=matriz,
            nit_formulario=self._nit_del_a1(payload_a1),
        )

    def _nit_del_a1(self, payload_a1: dict[str, Any]) -> Dato[str] | None:
        """El NIT del formulario ya lo extrajo el A1. Se reusa con su traza original."""
        bloque = (payload_a1.get("solicitante") or {}).get("nit_representante")
        if not bloque or bloque.get("valor") is None:
            return None
        traza_cruda = bloque.get("trazabilidad") or {}
        return Dato.extraido(
            str(bloque["valor"]),
            Traza(
                descripcion=traza_cruda.get("descripcion", "NIT segun el payload del A1"),
                modulo=traza_cruda.get("modulo"),
                seccion=traza_cruda.get("seccion"),
                pagina=traza_cruda.get("pagina"),
                campo=traza_cruda.get("campo"),
            ),
        )

    def _mapear_perfil(
        self, crudo: dict[str, Any], payload_a1: dict[str, Any]
    ) -> PerfilProducto:
        perfil_crudo = crudo.get("perfil_producto") or {}
        pagina = perfil_crudo.get("pagina")

        forma = _texto(perfil_crudo, "forma_de_la_sustancia", pagina)
        if not forma.presente:
            # El A1 ya extrajo la forma farmaceutica del FM113. Sirve de senal
            # secundaria antes que dejar la dimension indeterminada por omision.
            heredado = (payload_a1.get("producto") or {}).get("forma_farmaceutica") or {}
            if heredado.get("valor"):
                forma = Dato.extraido(
                    str(heredado["valor"]),
                    Traza(
                        descripcion=(heredado.get("trazabilidad") or {}).get(
                            "descripcion", "Forma farmaceutica segun el payload del A1"
                        )
                    ),
                )

        return PerfilProducto(
            forma_de_la_sustancia=forma,
            sistema_de_expresion=_texto(perfil_crudo, "sistema_de_expresion", pagina),
            banco_celular=_texto(perfil_crudo, "banco_celular", pagina),
            producto_referencia=_texto(perfil_crudo, "producto_referencia", pagina),
            modulos_presentes=tuple(perfil_crudo.get("modulos_presentes") or ()),
        )

    # -------------------------------------------------------------- auditoria

    def _log(
        self,
        dictamen: Dictamen,
        tipo: TipoEvento,
        accion: str,
        resultado: str,
        detalles: dict[str, Any] | None = None,
    ) -> None:
        self._d.auditoria.registrar(
            EventoAuditoria(
                momento=self._d.reloj(),
                tipo=tipo,
                radicado=dictamen.radicado,
                accion=accion,
                resultado=resultado,
                actor="AGENTE_A2_VICR",
                detalles=detalles or {},
            )
        )
