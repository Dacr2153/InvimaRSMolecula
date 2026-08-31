"""Lector determinista del Modulo 3 en Markdown.

Mismo papel que el extractor fake del A1: cero red, cero costo, resultado
identico en cada corrida, y toda la suite de pruebas apoyada aqui para que
desarrollar no consuma el credito de GCP.

Respeta el contrato del puerto: campo que no aparece, Dato.ausente. Ninguna
funcion de este archivo rellena, interpola ni deduce un valor faltante.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from ...domain.modelos import Especificacion, Medicion
from ...domain.modulo3 import ExpedienteCalidad
from ...domain.servicios.consistencia_lotes import Lote
from ...domain.servicios.envase_cierre import (
    CambioComponente,
    Componente,
    SistemaEnvaseCierre,
)
from ...domain.servicios.estabilidad import (
    CondicionEstabilidad,
    EstudioEstabilidad,
    PuntoMuestreo,
)
from ...domain.servicios.inactivacion_viral import (
    EtapaReduccionViral,
    ProcesoInactivacionViral,
)
from ...domain.servicios.sustancia_activa import SustanciaActiva
from ...domain.valores import Dato, Traza
from invima_nucleo.markdown import Documento, a_decimal, es_vacio, tabla_con

class LectorModulo3Markdown:
    """Adaptador de `ExpedienteCalidadPort` sobre un fixture en Markdown."""

    MODULO = "Modulo 3"

    def __init__(self, ruta: Path) -> None:
        self._ruta = Path(ruta)
        self._doc = Documento(self._ruta.read_text(encoding="utf-8"), self._ruta.name)

    @property
    def procedencia(self) -> str:
        return f"Lectura determinista del fixture {self._ruta.name} (sin modelo, sin red)"

    # -- utilidades de trazabilidad -------------------------------------------------

    def _traza(self, titulo_seccion: str, posicion: int, campo: str) -> Traza:
        return Traza.en_documento(
            modulo=self.MODULO,
            seccion=titulo_seccion,
            pagina=self._doc.pagina_en(posicion),
            campo=campo,
        )

    def _campo(self, seccion: tuple[str, int, str] | None, nombre: str) -> Dato[str]:
        if seccion is None:
            return Dato.ausente(nombre)
        titulo, inicio, cuerpo = seccion
        patron = re.compile(rf"^\s*{re.escape(nombre)}\s*:\s*(.+?)\s*$", re.MULTILINE)
        coincidencia = patron.search(cuerpo)
        if coincidencia is None or es_vacio(coincidencia.group(1)):
            return Dato.ausente(nombre)
        return Dato.extraido(
            coincidencia.group(1).strip(),
            self._traza(titulo, inicio + coincidencia.start(), nombre),
        )

    def _medicion(
        self,
        seccion: tuple[str, int, str],
        parametro: str,
        texto_valor: str,
        unidad: str,
    ) -> Medicion:
        titulo, inicio, _ = seccion
        if es_vacio(texto_valor):
            return Medicion(
                parametro=parametro,
                valor=Dato.ausente(parametro),
                unidad=unidad,
            )
        numero = a_decimal(texto_valor)
        valor: Decimal | str = numero if numero is not None else texto_valor
        return Medicion(
            parametro=parametro,
            valor=Dato.extraido(valor, self._traza(titulo, inicio, parametro)),
            unidad=unidad,
        )

    # -- secciones ------------------------------------------------------------------

    def _especificaciones(self) -> dict[str, Especificacion]:
        seccion = self._doc.seccion("Especificaciones declaradas")
        if seccion is None:
            return {}
        titulo, inicio, cuerpo = seccion
        tabla = tabla_con(cuerpo, ["parametro", "minimo", "maximo"])
        if tabla is None:
            return {}
        encabezado, filas = tabla
        indices = {c.lower(): i for i, c in enumerate(encabezado)}
        especificaciones: dict[str, Especificacion] = {}
        for fila in filas:
            def celda(nombre: str) -> str:
                indice = indices.get(nombre)
                return fila[indice] if indice is not None and indice < len(fila) else ""

            parametro = celda("parametro")
            if not parametro:
                continue
            minimo = None if es_vacio(celda("minimo")) else a_decimal(celda("minimo"))
            maximo = None if es_vacio(celda("maximo")) else a_decimal(celda("maximo"))
            esperado = "" if es_vacio(celda("valor esperado")) else celda("valor esperado")
            if minimo is None and maximo is None and not esperado:
                continue
            especificaciones[parametro] = Especificacion(
                parametro=parametro,
                unidad="" if es_vacio(celda("unidad")) else celda("unidad"),
                minimo=minimo,
                maximo=maximo,
                valor_esperado=esperado,
                fuente=self._traza(titulo, inicio, parametro),
            )
        return especificaciones

    def _mediciones_de_resultados(
        self, seccion: tuple[str, int, str] | None
    ) -> tuple[Medicion, ...]:
        if seccion is None:
            return ()
        tabla = tabla_con(seccion[2], ["parametro", "resultado"])
        if tabla is None:
            return ()
        encabezado, filas = tabla
        indices = {c.lower(): i for i, c in enumerate(encabezado)}
        mediciones: list[Medicion] = []
        for fila in filas:
            parametro = fila[indices["parametro"]] if indices["parametro"] < len(fila) else ""
            if not parametro:
                continue
            resultado = fila[indices["resultado"]] if indices["resultado"] < len(fila) else ""
            unidad_idx = indices.get("unidad")
            unidad = (
                fila[unidad_idx]
                if unidad_idx is not None and unidad_idx < len(fila) and not es_vacio(fila[unidad_idx])
                else ""
            )
            mediciones.append(self._medicion(seccion, parametro, resultado, unidad))
        return tuple(mediciones)

    def _sustancia_activa(self) -> SustanciaActiva:
        proceso = self._doc.seccion("Proceso de manufactura")
        caracterizacion = self._doc.seccion("Caracterizacion de la sustancia activa")
        mediciones = {m.parametro: m for m in self._mediciones_de_resultados(caracterizacion)}
        glicoformas = tuple(
            m for nombre, m in mediciones.items() if nombre.lower().startswith("glicoforma")
        )
        return SustanciaActiva(
            linea_celular=self._campo(proceso, "Linea celular"),
            sistema_expresion=self._campo(proceso, "Sistema de expresion"),
            viabilidad_banco_maestro=mediciones.get("Viabilidad del banco celular maestro"),
            viabilidad_banco_trabajo=mediciones.get("Viabilidad del banco celular de trabajo"),
            peso_molecular=mediciones.get("Masa molecular intacta"),
            perfil_glicosilacion=glicoformas,
        )

    def _proceso_viral(self) -> ProcesoInactivacionViral:
        seccion = self._doc.seccion("remocion e inactivacion viral")
        parametros = self._mediciones_de_resultados(seccion)
        etapas: list[EtapaReduccionViral] = []
        if seccion is not None:
            tabla = tabla_con(seccion[2], ["etapa", "lrv"])
            if tabla is not None:
                encabezado, filas = tabla
                indices = {c.lower(): i for i, c in enumerate(encabezado)}
                for fila in filas:
                    nombre = fila[indices["etapa"]] if indices["etapa"] < len(fila) else ""
                    if not nombre:
                        continue
                    lrv_texto = fila[indices["lrv"]] if indices["lrv"] < len(fila) else ""
                    virus_idx = indices.get("virus modelo")
                    virus_texto = (
                        fila[virus_idx]
                        if virus_idx is not None and virus_idx < len(fila)
                        else ""
                    )
                    virus = (
                        (
                            Dato.extraido(
                                virus_texto,
                                self._traza(seccion[0], seccion[1], f"Virus modelo de {nombre}"),
                            ),
                        )
                        if not es_vacio(virus_texto)
                        else ()
                    )
                    etapas.append(
                        EtapaReduccionViral(
                            nombre=nombre,
                            lrv=self._medicion(seccion, nombre, lrv_texto, "LRV"),
                            virus_modelo=virus,
                        )
                    )
        return ProcesoInactivacionViral(
            metodo=self._campo(seccion, "Metodo de inactivacion"),
            estudio_referencia=self._campo(seccion, "Estudio de referencia"),
            parametros_proceso=parametros,
            etapas=tuple(etapas),
        )

    def _lotes(self) -> tuple[Lote, ...]:
        seccion = self._doc.seccion("Resultados de liberacion de lotes")
        if seccion is None:
            return ()
        titulo, inicio, cuerpo = seccion
        tabla = tabla_con(cuerpo, ["parametro", "unidad"])
        if tabla is None:
            return ()
        encabezado, filas = tabla
        indices = {c.lower(): i for i, c in enumerate(encabezado)}
        columnas_lote = [
            (columna, posicion)
            for posicion, columna in enumerate(encabezado)
            if columna.lower() not in ("parametro", "unidad")
        ]
        mediciones: dict[str, list[Medicion]] = {c: [] for c, _ in columnas_lote}
        for fila in filas:
            parametro = fila[indices["parametro"]] if indices["parametro"] < len(fila) else ""
            if not parametro:
                continue
            unidad_idx = indices.get("unidad")
            unidad = (
                fila[unidad_idx]
                if unidad_idx is not None and unidad_idx < len(fila) and not es_vacio(fila[unidad_idx])
                else ""
            )
            for columna, posicion in columnas_lote:
                texto = fila[posicion] if posicion < len(fila) else ""
                mediciones[columna].append(
                    self._medicion(seccion, parametro, texto, unidad)
                )
        lotes: list[Lote] = []
        for columna, _ in columnas_lote:
            fecha_dato = self._campo(seccion, f"Lote {columna} fabricado")
            fecha = None
            if fecha_dato.presente:
                try:
                    fecha = date.fromisoformat(fecha_dato.exigir())
                except ValueError:
                    fecha = None
            lotes.append(
                Lote(
                    identificacion=columna,
                    fecha_fabricacion=fecha,
                    mediciones=tuple(mediciones[columna]),
                )
            )
        return tuple(lotes)

    def _estudios(self) -> tuple[EstudioEstabilidad, ...]:
        especificaciones = self._especificaciones()
        estudios: list[EstudioEstabilidad] = []
        for titulo, inicio, cuerpo in self._doc.secciones:
            if "estabilidad" not in titulo.lower():
                continue
            seccion = (titulo, inicio, cuerpo)
            parametro_dato = self._campo(seccion, "Parametro seguido")
            if not parametro_dato.presente:
                continue
            parametro = parametro_dato.exigir()
            tabla = tabla_con(cuerpo, ["mes", "resultado"])
            puntos: list[PuntoMuestreo] = []
            if tabla is not None:
                encabezado, filas = tabla
                indices = {c.lower(): i for i, c in enumerate(encabezado)}
                for fila in filas:
                    mes_texto = fila[indices["mes"]] if indices["mes"] < len(fila) else ""
                    mes = a_decimal(mes_texto)
                    if mes is None:
                        continue
                    resultado = (
                        fila[indices["resultado"]] if indices["resultado"] < len(fila) else ""
                    )
                    unidad_idx = indices.get("unidad")
                    unidad = (
                        fila[unidad_idx]
                        if unidad_idx is not None and unidad_idx < len(fila)
                        and not es_vacio(fila[unidad_idx])
                        else ""
                    )
                    puntos.append(
                        PuntoMuestreo(
                            mes=int(mes),
                            medicion=self._medicion(seccion, parametro, resultado, unidad),
                        )
                    )
            duracion_dato = self._campo(seccion, "Duracion declarada (meses)")
            duracion = (
                Dato.extraido(int(duracion_dato.exigir()), duracion_dato.traza)
                if duracion_dato.presente and duracion_dato.exigir().isdigit()
                else Dato.ausente("Duracion declarada (meses)")
            )
            humedad = self._campo(seccion, "Humedad relativa")
            estudios.append(
                EstudioEstabilidad(
                    condicion=CondicionEstabilidad(
                        nombre=self._campo(seccion, "Condicion").valor or titulo,
                        temperatura=self._campo(seccion, "Temperatura"),
                        humedad_relativa=humedad if humedad.presente else None,
                    ),
                    parametro=parametro,
                    especificacion=especificaciones.get(parametro),
                    puntos=tuple(puntos),
                    duracion_declarada_meses=duracion,
                )
            )
        return tuple(estudios)

    def _envase_cierre(self) -> SistemaEnvaseCierre:
        seccion = self._doc.seccion("Sistema envase-cierre")
        if seccion is None:
            return SistemaEnvaseCierre()
        titulo, inicio, cuerpo = seccion
        componentes: list[Componente] = []
        tabla = tabla_con(cuerpo, ["componente", "material"])
        if tabla is not None:
            encabezado, filas = tabla
            indices = {c.lower(): i for i, c in enumerate(encabezado)}
            for fila in filas:
                nombre = fila[indices["componente"]] if indices["componente"] < len(fila) else ""
                if not nombre:
                    continue
                material_texto = (
                    fila[indices["material"]] if indices["material"] < len(fila) else ""
                )
                norma_idx = indices.get("norma")
                norma_texto = (
                    fila[norma_idx] if norma_idx is not None and norma_idx < len(fila) else ""
                )
                componentes.append(
                    Componente(
                        nombre=nombre,
                        material=(
                            Dato.ausente(f"Material de {nombre}")
                            if es_vacio(material_texto)
                            else Dato.extraido(
                                material_texto, self._traza(titulo, inicio, f"Material de {nombre}")
                            )
                        ),
                        norma_referencia=(
                            None
                            if es_vacio(norma_texto)
                            else Dato.extraido(
                                norma_texto, self._traza(titulo, inicio, f"Norma de {nombre}")
                            )
                        ),
                    )
                )
        cambios: list[CambioComponente] = []
        componente_cambiado = self._campo(seccion, "Cambio de componente")
        if componente_cambiado.presente:
            fecha_dato = self._campo(seccion, "Fecha efectiva del cambio")
            fecha: Dato[date] | None = None
            if fecha_dato.presente:
                try:
                    fecha = Dato.extraido(
                        date.fromisoformat(fecha_dato.exigir()), fecha_dato.traza
                    )
                except ValueError:
                    fecha = Dato.ausente("Fecha efectiva del cambio")
            estudio = self._campo(seccion, "Estudio comparativo")
            cambios.append(
                CambioComponente(
                    componente=componente_cambiado.exigir(),
                    material_previo=self._campo(seccion, "Material previo"),
                    material_nuevo=self._campo(seccion, "Material nuevo"),
                    fecha_efectiva=fecha,
                    estudio_comparativo=estudio if estudio.presente else None,
                )
            )
        return SistemaEnvaseCierre(
            componentes=tuple(componentes),
            ensayos=self._mediciones_de_resultados(seccion),
            cambios=tuple(cambios),
        )

    def _textos_libres(self) -> tuple[tuple[str, str], ...]:
        textos: list[tuple[str, str]] = []
        for titulo, _, cuerpo in self._doc.secciones:
            patron = re.compile(r"^\s*Observaciones\s*:\s*(.+?)(?=\n\s*\n|\Z)", re.MULTILINE | re.DOTALL)
            for coincidencia in patron.finditer(cuerpo):
                textos.append((f"{titulo} > Observaciones", coincidencia.group(1).strip()))
        return tuple(textos)

    # -- puerto ---------------------------------------------------------------------

    def leer(self, radicado: str) -> ExpedienteCalidad:
        producto = re.search(
            r"^\s*Nombre del Producto\s*:\s*(.+?)\s*$", self._doc.markdown, re.MULTILINE
        )
        return ExpedienteCalidad(
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
            sustancia_activa=self._sustancia_activa(),
            proceso_viral=self._proceso_viral(),
            envase_cierre=self._envase_cierre(),
            especificaciones_declaradas=self._especificaciones(),
            lotes=self._lotes(),
            estudios_estabilidad=self._estudios(),
            textos_libres=self._textos_libres(),
        )
