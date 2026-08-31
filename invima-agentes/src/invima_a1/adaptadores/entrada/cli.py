"""Interfaz de linea de comandos del agente A1-RCE.

Dos verbos, y esa separacion es intencional:

    procesar : corre el agente. Termina SIEMPRE en PENDIENTE_VALIDACION_HUMANA.
    decidir  : registra la decision de un servidor publico. Solo esto enruta.

No existe una bandera que combine ambos. Enrutar sin persona es imposible por
diseno, no por convencion.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ...aplicacion.procesar_radicacion import (
    ProcesarRadicacionUseCase,
    ResultadoProcesamiento,
)
from ...aplicacion.supervision import RegistrarDecisionHumana
from ...config import Ajustes, ahora, construir_dependencias
from ...domain.errores import TransicionIlegalError
from ...domain.estados import SentidoDecision

app = typer.Typer(
    add_completion=False,
    help="Agente A1-RCE: receptor, clasificador y enrutador de expedientes CTD.",
)
consola = Console()

_COLOR_ORIGEN = {
    "EXTRAIDO": "cyan",
    "BUSQUEDA": "green",
    "RECOMENDACION": "yellow",
    "NO_SUMINISTRADO": "dim",
}


def _radicado_por_defecto() -> str:
    return f"2026-REG-{datetime.now(UTC).strftime('%m%d%H%M%S')}"


def _tabla_campos(titulo: str, bloque: dict) -> Table:
    tabla = Table(title=titulo, title_justify="left", show_lines=False)
    tabla.add_column("Campo", style="bold")
    tabla.add_column("Valor")
    tabla.add_column("Origen")
    tabla.add_column("Trazabilidad", overflow="fold")

    for campo, dato in bloque.items():
        if not isinstance(dato, dict) or "origen" not in dato:
            continue
        origen = dato["origen"]
        traza = (dato.get("trazabilidad") or {}).get("descripcion", "")
        tabla.add_row(
            campo,
            str(dato.get("valor")) if dato.get("valor") is not None else "-",
            f"[{_COLOR_ORIGEN.get(origen, 'white')}]{origen}[/]",
            traza,
        )
    return tabla


def _mostrar(resultado: ResultadoProcesamiento) -> None:
    payload = resultado.payload
    expediente = resultado.expediente

    consola.print(
        Panel(
            f"[bold]{expediente.radicado}[/]\nEstado: [bold]{expediente.estado}[/]",
            title="Checklist Inteligente de Entrada",
            border_style="blue",
        )
    )

    consola.print(_tabla_campos("Solicitante", payload["solicitante"]))
    consola.print(_tabla_campos("Producto", payload["producto"]))
    consola.print(_tabla_campos("Datos de pago", payload["radicacion"]["pago"]))

    pago = payload["radicacion"]["pago"]
    estilo = "green" if pago["verificado"] else "red"
    consola.print(
        Panel(pago["resultado_validacion"], title="Validacion transaccional", border_style=estilo)
    )

    normativa = payload.get("evaluacion_normativa")
    if normativa:
        consola.print(_tabla_campos("Evaluacion normativa", normativa))
        discrepancia = normativa.get("discrepancia_declarativa")
        if discrepancia:
            consola.print(
                Panel(discrepancia["mensaje"], title="Discrepancia declarativa", border_style="yellow")
            )

    internacional = payload["validaciones_internacionales"].get(
        "reporte_coincidencia_internacional"
    )
    if internacional and internacional["contrastes"]:
        tabla = Table(title="Contraste contra agencias de referencia", title_justify="left")
        tabla.add_column("Agencia", style="bold")
        tabla.add_column("Clase")
        tabla.add_column("Observacion", overflow="fold")
        tabla.add_column("Fuente", overflow="fold")
        for contraste in internacional["contrastes"]:
            tabla.add_row(
                contraste["agencia"],
                contraste["clase_contraste"],
                contraste["observacion"],
                contraste["fuente"] or "-",
            )
        consola.print(tabla)
        if internacional["aprobaciones_declaradas_no_verificadas"]:
            consola.print(
                Panel(
                    "Declaradas por el solicitante y NO verificadas en fuente publica: "
                    + ", ".join(internacional["aprobaciones_declaradas_no_verificadas"]),
                    border_style="yellow",
                )
            )

    enrutamiento = payload.get("enrutamiento")
    if enrutamiento:
        consola.print(
            Panel(
                f"Ruta: [bold]{enrutamiento['ruta_recomendada']['valor']}[/]\n"
                f"Destino: {enrutamiento['destino_primario']['valor']}\n"
                f"Paralelos: {', '.join(enrutamiento['destinos_paralelos']) or '-'}\n"
                f"Prioridad: {enrutamiento['prioridad']['valor']}\n\n"
                f"{enrutamiento['razon']}",
                title="Recomendacion de enrutamiento (no vinculante)",
                border_style="yellow",
            )
        )

    sospechoso = payload["seguridad_y_trazabilidad"]["contenido_sospechoso_detectado"]
    if sospechoso:
        tabla = Table(title="Contenido sospechoso neutralizado", title_justify="left")
        tabla.add_column("Campo")
        tabla.add_column("Motivo")
        tabla.add_column("Fragmento", overflow="fold")
        for hallazgo in sospechoso:
            tabla.add_row(hallazgo["campo"], hallazgo["motivo"], hallazgo["fragmento"])
        consola.print(tabla)

    consola.print(
        Panel(
            payload["supervision_humana"]["advertencia"],
            title=f"[bold]{payload['supervision_humana']['estado']}[/]",
            border_style="red",
        )
    )


@app.command()
def procesar(
    dossier: Annotated[Path, typer.Argument(help="Carpeta del dossier a procesar")],
    radicado: Annotated[str, typer.Option(help="Numero de radicado")] = "",
    offline: Annotated[bool, typer.Option(help="Sin red ni consumo de credito")] = True,
    modelo: Annotated[str, typer.Option(help="Modelo a usar si no es offline")] = "",
    salida: Annotated[Path | None, typer.Option(help="Ruta del payload JSON")] = None,
    json_only: Annotated[bool, typer.Option("--json", help="Solo imprimir el JSON")] = False,
) -> None:
    """Ejecuta el agente sobre un dossier. Termina esperando validacion humana."""
    ajustes = Ajustes.desde_entorno(offline=offline, modelo=modelo or None)
    caso = ProcesarRadicacionUseCase(construir_dependencias(ajustes))
    resultado = caso.ejecutar(dossier, radicado or _radicado_por_defecto())

    if json_only:
        print(json.dumps(resultado.payload, ensure_ascii=False, indent=2))
    else:
        _mostrar(resultado)

    if salida:
        salida.parent.mkdir(parents=True, exist_ok=True)
        salida.write_text(
            json.dumps(resultado.payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if not json_only:
            consola.print(f"Payload escrito en {salida}")

    if not json_only:
        consola.print(
            f"\nPara continuar el tramite un evaluador debe decidir:\n"
            f"  invima-a1 decidir {resultado.expediente.radicado} "
            f"--usuario <nombre> --sentido aprobar"
        )


@app.command()
def decidir(
    radicado: Annotated[str, typer.Argument(help="Radicado del expediente")],
    usuario: Annotated[str, typer.Option(help="Servidor publico que decide")],
    sentido: Annotated[
        str, typer.Option(help="aprobar | corregir | devolver")
    ] = "aprobar",
    observaciones: Annotated[str, typer.Option(help="Observaciones del evaluador")] = "",
    campos: Annotated[str, typer.Option(help="Campos corregidos, separados por coma")] = "",
) -> None:
    """Registra la decision del evaluador. Unica via para sacar el expediente del gate."""
    mapa = {
        "aprobar": SentidoDecision.APROBAR_ENRUTAMIENTO,
        "corregir": SentidoDecision.CORREGIR_Y_APROBAR,
        "devolver": SentidoDecision.DEVOLVER,
    }
    if sentido not in mapa:
        consola.print(f"[red]Sentido no valido: {sentido}. Usa: {', '.join(mapa)}[/]")
        raise typer.Exit(code=2)

    ajustes = Ajustes.desde_entorno(offline=True)
    deps = construir_dependencias(ajustes)
    accion = RegistrarDecisionHumana(
        repositorio=deps.repositorio, auditoria=deps.auditoria, reloj=ahora
    )

    try:
        payload = accion.ejecutar(
            radicado=radicado,
            usuario=usuario,
            sentido=mapa[sentido],
            observaciones=observaciones,
            campos_corregidos=tuple(c.strip() for c in campos.split(",") if c.strip()),
        )
    except TransicionIlegalError as error:
        consola.print(f"[red]{error}[/]")
        raise typer.Exit(code=1) from error

    consola.print(
        Panel(
            f"Estado: [bold]{payload['radicacion']['estado']}[/]\n"
            f"Responsable: {payload['supervision_humana']['usuario_responsable']}\n"
            f"Sentido: {payload['supervision_humana']['sentido_decision']}\n"
            f"Firma: {payload['supervision_humana']['firma_timestamp']}",
            title="Decision registrada",
            border_style="green",
        )
    )


@app.command()
def modelos() -> None:
    """Lista los modelos de Gemini disponibles para tu API key.

    Sirve para no adivinar el identificador del modelo: los alias cambian.
    Listar no consume credito.
    """
    ajustes = Ajustes.desde_entorno(offline=False)
    if not ajustes.api_key:
        consola.print("[red]Falta GEMINI_API_KEY. Copia .env.ejemplo a .env.[/]")
        raise typer.Exit(code=2)

    from google import genai

    cliente = genai.Client(api_key=ajustes.api_key)
    tabla = Table(title="Modelos disponibles", title_justify="left")
    tabla.add_column("Modelo", style="bold")
    tabla.add_column("Contexto entrada")
    tabla.add_column("Recomendado para")

    for modelo in cliente.models.list():
        nombre = modelo.name.removeprefix("models/")
        acciones = getattr(modelo, "supported_actions", None) or []
        if "generateContent" not in acciones:
            continue
        if "flash" in nombre:
            uso = "Extraccion (A1) - barato"
        elif "pro" in nombre:
            uso = "Razonamiento (A3/A4)"
        else:
            uso = "-"
        tabla.add_row(nombre, str(getattr(modelo, "input_token_limit", "-")), uso)

    consola.print(tabla)


@app.command()
def verificar(
    modelo: Annotated[str, typer.Option(help="Modelo a probar")] = "",
) -> None:
    """Comprueba la conexion real con Gemini con una llamada minima.

    Manda un fragmento de formulario de tres lineas y valida que vuelva JSON
    con la estructura esperada. Cuesta una fraccion de centavo: es lo que hay
    que gastar antes de lanzar un dossier completo.
    """
    ajustes = Ajustes.desde_entorno(offline=False, modelo=modelo or None)
    if not ajustes.api_key:
        consola.print(
            "[red]Falta GEMINI_API_KEY.[/]\n"
            "  1. Crea la key en https://aistudio.google.com/apikey\n"
            "     seleccionando el proyecto vinculado al billing del evento.\n"
            "  2. cp .env.ejemplo .env  y pega la key ahi."
        )
        raise typer.Exit(code=2)

    from ...adaptadores.salida.extractor_gemini import ExtractorGemini

    muestra = (
        "## Seccion 1. Datos del Solicitante\n"
        "Razon Social del Titular: LABORATORIO DE PRUEBA S.A.S.\n"
        "NIT: 900.000.000-0\n"
    )
    esquema = {
        "type": "object",
        "properties": {
            "nombre_titular": {"type": ["string", "null"]},
            "nit": {"type": ["string", "null"]},
            "campo_que_no_existe": {"type": ["string", "null"]},
        },
        "required": ["nombre_titular"],
    }
    instruccion = (
        "Extrae los campos del fragmento delimitado. Si un campo no aparece "
        "explicitamente, devuelve null. No infieras."
    )

    extractor = ExtractorGemini(api_key=ajustes.api_key, modelo=ajustes.modelo)
    consola.print(f"Probando [bold]{extractor.identificador_modelo}[/] ...")

    try:
        salida = extractor.extraer(muestra, esquema, instruccion)
    except Exception as error:  # noqa: BLE001 - se reporta tal cual al usuario
        consola.print(Panel(str(error), title="Fallo la conexion", border_style="red"))
        raise typer.Exit(code=1) from error

    tabla = Table(title="Respuesta del modelo", title_justify="left")
    tabla.add_column("Campo", style="bold")
    tabla.add_column("Valor")
    for clave, valor in salida.items():
        tabla.add_row(clave, "null" if valor is None else str(valor))
    consola.print(tabla)

    problemas: list[str] = []
    if not salida.get("nombre_titular"):
        problemas.append("No extrajo el titular, que si esta en el fragmento.")
    if salida.get("campo_que_no_existe") is not None:
        problemas.append(
            "Invento un valor para un campo ausente. La regla de no inferir no "
            "se esta respetando: revisa el prompt del extractor."
        )

    if problemas:
        consola.print(
            Panel("\n".join(problemas), title="Conexion OK, comportamiento NO", border_style="yellow")
        )
        raise typer.Exit(code=1)

    consola.print(
        Panel(
            "Conexion establecida y comportamiento correcto: extrajo lo presente "
            "y devolvio null para lo ausente.\n\n"
            "Siguiente paso:\n"
            "  invima-a1 procesar data/fixtures/dossier_corazilimab --no-offline",
            title="Verificacion superada",
            border_style="green",
        )
    )


def main() -> None:
    app()


if __name__ == "__main__":
    sys.exit(app())
