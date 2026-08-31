"""Lector determinista de los Modulos 4, 5 y 7 en Markdown.

Cero red, cero costo, resultado identico en cada corrida. Respeta el contrato
del puerto: campo que no aparece, Dato.ausente. Ninguna funcion de este archivo
completa un parametro clinico con el valor tipico de la clase terapeutica.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path
from typing import Any

from invima_nucleo.markdown import Documento, a_decimal, es_vacio, tabla_con

from ...domain.modelos import Medicion
from ...domain.modulo45 import ExpedienteEvidencia
from ...domain.servicios.cruce_toxico_clinico import PlanGestionRiesgos
from ...domain.servicios.ensayo_pivotal import Desenlace, EnsayoPivotal, TipoDesenlace
from ...domain.servicios.farmacovigilancia import InformePBRER, SenalSeguridad
from ...domain.servicios.inmunogenicidad import ImpactoDeclarado, Inmunogenicidad
from ...domain.servicios.preclinico import (
    EstudioFarmacocinetico,
    EstudioReproductivo,
    EstudioToxicologia,
    Malformacion,
)
from ...domain.valores import Dato, Traza

Seccion = tuple[str, int, str]


class LectorEvidenciaMarkdown:
    """Adaptador de `ExpedienteEvidenciaPort` sobre un fixture en Markdown."""

    MODULO = "Modulos 4, 5 y 7"

    def __init__(self, ruta: Path) -> None:
        self._ruta = Path(ruta)
        self._doc = Documento(self._ruta.read_text(encoding="utf-8"), self._ruta.name)

    @property
    def procedencia(self) -> str:
        return f"Lectura determinista del fixture {self._ruta.name} (sin modelo, sin red)"

    # -- utilidades -----------------------------------------------------------------

    def _traza(self, seccion: Seccion, campo: str) -> Traza:
        return Traza.en_documento(
            modulo=self.MODULO,
            seccion=seccion[0],
            pagina=self._doc.pagina_en(seccion[1]),
            campo=campo,
        )

    def _campo(self, seccion: Seccion | None, nombre: str) -> Dato[str]:
        if seccion is None:
            return Dato.ausente(nombre)
        patron = re.compile(rf"^\s*{re.escape(nombre)}\s*:\s*(.+?)\s*$", re.MULTILINE)
        coincidencia = patron.search(seccion[2])
        if coincidencia is None or es_vacio(coincidencia.group(1)):
            return Dato.ausente(nombre)
        return Dato.extraido(coincidencia.group(1).strip(), self._traza(seccion, nombre))

    def _numero(self, seccion: Seccion | None, nombre: str) -> Dato[Decimal]:
        crudo = self._campo(seccion, nombre)
        if not crudo.presente:
            return Dato.ausente(nombre)
        valor = a_decimal(crudo.exigir())
        if valor is None:
            return Dato.ausente(nombre)
        return Dato.extraido(valor, crudo.traza)

    def _medicion_campo(
        self, seccion: Seccion | None, nombre: str, unidad: str = "", parametro: str | None = None
    ) -> Medicion | None:
        if seccion is None:
            return None
        dato = self._numero(seccion, nombre)
        if not dato.presente:
            return None
        return Medicion(parametro=parametro or nombre, valor=dato, unidad=unidad)

    def _medicion_celda(
        self, seccion: Seccion, parametro: str, texto: str, unidad: str
    ) -> Medicion:
        if es_vacio(texto):
            return Medicion(parametro=parametro, valor=Dato.ausente(parametro), unidad=unidad)
        numero = a_decimal(texto)
        valor: Decimal | str = numero if numero is not None else texto
        return Medicion(
            parametro=parametro,
            valor=Dato.extraido(valor, self._traza(seccion, parametro)),
            unidad=unidad,
        )

    def _dato_celda(self, seccion: Seccion, campo: str, texto: str) -> Dato[str] | None:
        if es_vacio(texto):
            return None
        return Dato.extraido(texto, self._traza(seccion, campo))

    def _filas(self, seccion: Seccion, columnas: tuple[str, ...]):
        tabla = tabla_con(seccion[2], columnas)
        if tabla is None:
            return
        encabezado, filas = tabla
        indices = {c.lower(): i for i, c in enumerate(encabezado)}

        def celda(fila: list[str], nombre: str) -> str:
            indice = indices.get(nombre.lower())
            return fila[indice] if indice is not None and indice < len(fila) else ""

        for fila in filas:
            yield fila, celda

    def _mediciones_parametro(self, seccion: Seccion | None) -> tuple[Medicion, ...]:
        if seccion is None:
            return ()
        mediciones: list[Medicion] = []
        for fila, celda in self._filas(seccion, ("parametro", "resultado")):
            parametro = celda(fila, "parametro")
            if not parametro:
                continue
            unidad = celda(fila, "unidad")
            mediciones.append(
                self._medicion_celda(
                    seccion, parametro, celda(fila, "resultado"),
                    "" if es_vacio(unidad) else unidad,
                )
            )
        return tuple(mediciones)

    # -- secciones ------------------------------------------------------------------

    def _farmacocinetica(self) -> EstudioFarmacocinetico | None:
        seccion = self._doc.seccion("Farmacocinetica en animal")
        if seccion is None:
            return None
        return EstudioFarmacocinetico(
            estudio_id=self._campo(seccion, "Identificacion del estudio"),
            especie=self._campo(seccion, "Especie"),
            ruta_administracion=self._campo(seccion, "Ruta de administracion"),
            dosis=None,
            parametros=self._mediciones_parametro(seccion),
        )

    def _toxicologia(self) -> tuple[EstudioToxicologia, ...]:
        seccion = self._doc.seccion("Toxicologia de dosis repetidas")
        if seccion is None:
            return ()
        unidad = self._campo(seccion, "Unidad de dosis")
        unidad_dosis = unidad.valor if unidad.presente else ""
        organo = self._campo(seccion, "Organo blanco")
        reversibilidad = self._campo(seccion, "Reversibilidad")
        margen = self._numero(seccion, "Margen de seguridad declarado")
        return (
            EstudioToxicologia(
                estudio_id=self._campo(seccion, "Identificacion del estudio"),
                especie=self._campo(seccion, "Especie"),
                duracion_semanas=self._medicion_campo(
                    seccion, "Duracion en semanas", "semanas"
                ),
                noael=self._medicion_campo(seccion, "NOAEL", unidad_dosis),
                loael=self._medicion_campo(seccion, "LOAEL", unidad_dosis),
                organo_blanco=organo if organo.presente else None,
                hallazgos_cuantificados=self._mediciones_parametro(seccion),
                reversibilidad=reversibilidad if reversibilidad.presente else None,
                dosis_clinica_equivalente=self._medicion_campo(
                    seccion, "Dosis clinica equivalente", unidad_dosis
                ),
                margen_seguridad_declarado=margen if margen.presente else None,
            ),
        )

    def _reproductiva(self) -> EstudioReproductivo | None:
        seccion = self._doc.seccion("Toxicologia reproductiva")
        if seccion is None:
            return None
        malformaciones: list[Malformacion] = []
        for fila, celda in self._filas(seccion, ("malformacion", "descripcion")):
            tipo = celda(fila, "malformacion")
            if not tipo:
                continue
            frecuencia_texto = celda(fila, "frecuencia")
            malformaciones.append(
                Malformacion(
                    tipo=Dato.extraido(tipo, self._traza(seccion, f"Malformacion {tipo}")),
                    descripcion=self._dato_celda(
                        seccion, f"Descripcion de {tipo}", celda(fila, "descripcion")
                    ),
                    frecuencia=(
                        None
                        if es_vacio(frecuencia_texto)
                        else self._medicion_celda(
                            seccion, f"Frecuencia de {tipo}", frecuencia_texto, ""
                        )
                    ),
                )
            )
        periodo = self._campo(seccion, "Periodo de exposicion")
        abortos = self._campo(seccion, "Abortos espontaneos")
        categoria = self._campo(seccion, "Categoria de riesgo en embarazo declarada")
        mitigacion = self._campo(seccion, "Medida de mitigacion declarada")
        return EstudioReproductivo(
            estudio_id=self._campo(seccion, "Identificacion del estudio"),
            modelo=self._campo(seccion, "Modelo"),
            periodo_exposicion=periodo if periodo.presente else None,
            dosis_materna=self._medicion_campo(seccion, "Dosis materna", "mg/kg"),
            abortos_espontaneos=abortos if abortos.presente else None,
            transferencia_placentaria=self._medicion_campo(
                seccion, "Transferencia placentaria", "%"
            ),
            malformaciones=tuple(malformaciones),
            categoria_embarazo_declarada=categoria if categoria.presente else None,
            medida_mitigacion_declarada=mitigacion if mitigacion.presente else None,
        )

    def _ensayo(self) -> EnsayoPivotal | None:
        seccion = self._doc.seccion("Ensayo clinico pivotal")
        if seccion is None:
            return None
        desenlaces: list[Desenlace] = []
        for fila, celda in self._filas(seccion, ("desenlace", "tipo")):
            metrica = celda(fila, "desenlace")
            if not metrica:
                continue
            crudo_tipo = celda(fila, "tipo").strip().upper()
            try:
                tipo = TipoDesenlace(crudo_tipo)
            except ValueError:
                tipo = TipoDesenlace.SECUNDARIO
            unidad = celda(fila, "unidad")
            unidad = "" if es_vacio(unidad) else unidad
            diferencia = celda(fila, "diferencia declarada")
            p_valor = celda(fila, "valor p")
            desenlaces.append(
                Desenlace(
                    metrica=metrica,
                    tipo=tipo,
                    valor_intervencion=self._medicion_celda(
                        seccion, f"{metrica} (intervencion)", celda(fila, "intervencion"), unidad
                    ),
                    valor_control=self._medicion_celda(
                        seccion, f"{metrica} (control)", celda(fila, "control"), unidad
                    ),
                    diferencia_declarada=(
                        None
                        if es_vacio(diferencia) or a_decimal(diferencia) is None
                        else Dato.extraido(
                            a_decimal(diferencia),
                            self._traza(seccion, f"{metrica} (diferencia declarada)"),
                        )
                    ),
                    p_valor=(
                        None
                        if es_vacio(p_valor) or a_decimal(p_valor) is None
                        else Dato.extraido(
                            a_decimal(p_valor), self._traza(seccion, f"{metrica} (valor p)")
                        )
                    ),
                    significancia_declarada=self._dato_celda(
                        seccion, f"{metrica} (significancia declarada)",
                        celda(fila, "significancia declarada"),
                    ),
                    intervalo_confianza=self._dato_celda(
                        seccion, f"{metrica} (intervalo de confianza)",
                        celda(fila, "intervalo de confianza"),
                    ),
                )
            )

        poblaciones_crudas = self._campo(seccion, "Poblaciones de analisis")
        poblaciones: tuple[Dato[str], ...] = ()
        if poblaciones_crudas.presente:
            poblaciones = tuple(
                Dato.extraido(parte.strip(), poblaciones_crudas.traza)
                for parte in str(poblaciones_crudas.exigir()).split(";")
                if parte.strip()
            )

        alfa = self._numero(seccion, "Nivel de significancia preespecificado")
        poder = self._numero(seccion, "Poder estadistico declarado")
        multiplicidad = self._campo(seccion, "Control de multiplicidad")
        return EnsayoPivotal(
            estudio_id=self._campo(seccion, "Identificacion del estudio"),
            registro_publico=self._campo(seccion, "Registro publico"),
            fase=self._campo(seccion, "Fase"),
            diseno=self._campo(seccion, "Diseno"),
            poblacion=self._campo(seccion, "Poblacion"),
            intervencion=self._campo(seccion, "Intervencion"),
            comparador=self._campo(seccion, "Comparador"),
            duracion_semanas=self._medicion_campo(seccion, "Duracion en semanas", "semanas"),
            n_total=self._medicion_campo(seccion, "Poblacion total", "pacientes"),
            n_intervencion=self._medicion_campo(
                seccion, "Pacientes en el brazo de intervencion", "pacientes"
            ),
            n_control=self._medicion_campo(
                seccion, "Pacientes en el brazo de control", "pacientes"
            ),
            alfa_prespecificado=alfa if alfa.presente else None,
            poder_declarado=poder if poder.presente else None,
            diferencia_del_calculo_de_poder=self._medicion_campo(
                seccion, "Diferencia usada en el calculo de poder"
            ),
            control_multiplicidad=multiplicidad if multiplicidad.presente else None,
            poblaciones_de_analisis=poblaciones,
            desenlaces=tuple(desenlaces),
        )

    def _inmunogenicidad(self) -> Inmunogenicidad | None:
        seccion = self._doc.seccion("Inmunogenicidad")
        if seccion is None:
            return None
        impactos: list[ImpactoDeclarado] = []
        for fila, celda in self._filas(seccion, ("metrica", "valor p")):
            metrica = celda(fila, "metrica")
            if not metrica:
                continue
            p_valor = celda(fila, "valor p")
            impactos.append(
                ImpactoDeclarado(
                    metrica=metrica,
                    p_valor=(
                        None
                        if es_vacio(p_valor) or a_decimal(p_valor) is None
                        else Dato.extraido(
                            a_decimal(p_valor), self._traza(seccion, f"{metrica} (valor p)")
                        )
                    ),
                    conclusion_declarada=self._dato_celda(
                        seccion, f"{metrica} (conclusion)", celda(fila, "conclusion declarada")
                    ),
                    intervalo_confianza=self._dato_celda(
                        seccion, f"{metrica} (intervalo de confianza)",
                        celda(fila, "intervalo de confianza"),
                    ),
                )
            )
        ada_incidencia = self._numero(seccion, "Incidencia ADA declarada")
        nab_incidencia = self._numero(seccion, "Incidencia NAb declarada")
        ventana = self._campo(seccion, "Ventana de aparicion")
        return Inmunogenicidad(
            ada_casos=self._medicion_campo(seccion, "Casos ADA", "casos"),
            ada_poblacion=self._medicion_campo(seccion, "Poblacion evaluada ADA", "pacientes"),
            ada_incidencia_declarada=ada_incidencia if ada_incidencia.presente else None,
            nab_casos=self._medicion_campo(seccion, "Casos NAb", "casos"),
            nab_poblacion=self._medicion_campo(seccion, "Poblacion evaluada NAb", "pacientes"),
            nab_incidencia_declarada=nab_incidencia if nab_incidencia.presente else None,
            ventana_aparicion=ventana if ventana.presente else None,
            impactos=tuple(impactos),
        )

    def _pbrer(self) -> InformePBRER | None:
        seccion = self._doc.seccion("Informe periodico")
        if seccion is None:
            return None
        senales: list[SenalSeguridad] = []
        for fila, celda in self._filas(seccion, ("senal", "descripcion")):
            identificador = celda(fila, "senal")
            if not identificador:
                continue
            tasa = celda(fila, "tasa declarada por 1000 pacientes-ano")
            senales.append(
                SenalSeguridad(
                    identificador=identificador,
                    descripcion=Dato.extraido(
                        celda(fila, "descripcion"),
                        self._traza(seccion, f"Senal {identificador}"),
                    ),
                    casos=self._medicion_celda(
                        seccion, f"Casos de {identificador}", celda(fila, "casos"), "casos"
                    ),
                    tasa_declarada_por_1000=(
                        None
                        if es_vacio(tasa) or a_decimal(tasa) is None
                        else Dato.extraido(
                            a_decimal(tasa), self._traza(seccion, f"Tasa de {identificador}")
                        )
                    ),
                    sistema_organo=self._dato_celda(
                        seccion, f"Sistema de {identificador}", celda(fila, "sistema u organo")
                    ),
                    factor_riesgo=self._dato_celda(
                        seccion, f"Factor de riesgo de {identificador}",
                        celda(fila, "factor de riesgo"),
                    ),
                    gravedad=self._dato_celda(
                        seccion, f"Gravedad de {identificador}", celda(fila, "gravedad")
                    ),
                )
            )
        general = self._numero(seccion, "Incidencia general declarada")
        graves = self._numero(seccion, "Incidencia de graves declarada")
        estado = self._campo(seccion, "Estado de la investigacion de muertes")
        return InformePBRER(
            numero=self._campo(seccion, "Numero de informe"),
            periodo_meses=self._medicion_campo(seccion, "Periodo de observacion en meses", "meses"),
            exposicion_pacientes_ano=self._medicion_campo(
                seccion, "Exposicion acumulada en pacientes-ano", "pacientes-ano"
            ),
            pacientes_expuestos=self._medicion_campo(seccion, "Pacientes expuestos", "pacientes"),
            eventos_totales=self._medicion_campo(seccion, "Eventos adversos totales", "eventos"),
            incidencia_general_declarada=general if general.presente else None,
            eventos_graves=self._medicion_campo(seccion, "Eventos adversos graves", "eventos"),
            incidencia_graves_declarada=graves if graves.presente else None,
            muertes=self._medicion_campo(seccion, "Muertes con relacion potencial", "casos"),
            estado_investigacion_muertes=estado if estado.presente else None,
            senales=tuple(senales),
        )

    def _plan_riesgos(self) -> PlanGestionRiesgos | None:
        seccion = self._doc.seccion("Plan de gestion de riesgos")
        if seccion is None:
            return None
        riesgos: list[Dato[str]] = []
        for fila, celda in self._filas(seccion, ("riesgo listado",)):
            texto = celda(fila, "riesgo listado")
            if es_vacio(texto):
                continue
            riesgos.append(
                Dato.extraido(texto, self._traza(seccion, "Riesgo listado en el PGR"))
            )
        return PlanGestionRiesgos(
            version=self._campo(seccion, "Version del plan"),
            riesgos_listados=tuple(riesgos),
        )

    def _textos_libres(self) -> tuple[tuple[str, str], ...]:
        textos: list[tuple[str, str]] = []
        patron = re.compile(
            r"^\s*Observaciones\s*:\s*(.+?)(?=\n\s*\n|\Z)", re.MULTILINE | re.DOTALL
        )
        for titulo, _, cuerpo in self._doc.secciones:
            for coincidencia in patron.finditer(cuerpo):
                textos.append((f"{titulo} > Observaciones", coincidencia.group(1).strip()))
        return tuple(textos)

    # -- puerto ---------------------------------------------------------------------

    def leer(self, radicado: str) -> ExpedienteEvidencia:
        producto = re.search(
            r"^\s*Nombre del Producto\s*:\s*(.+?)\s*$", self._doc.markdown, re.MULTILINE
        )
        return ExpedienteEvidencia(
            radicado=radicado,
            producto=(
                Dato.extraido(
                    producto.group(1),
                    Traza.en_documento(
                        modulo=self.MODULO,
                        seccion="Portada",
                        pagina=self._doc.pagina_en(producto.start()),
                        campo="Nombre del Producto",
                    ),
                )
                if producto
                else Dato.ausente("Nombre del Producto")
            ),
            farmacocinetica=self._farmacocinetica(),
            toxicologia=self._toxicologia(),
            reproductiva=self._reproductiva(),
            ensayo_pivotal=self._ensayo(),
            inmunogenicidad=self._inmunogenicidad(),
            pbrer=self._pbrer(),
            plan_riesgos=self._plan_riesgos(),
            especificaciones_declaradas={},
            textos_libres=self._textos_libres(),
        )
