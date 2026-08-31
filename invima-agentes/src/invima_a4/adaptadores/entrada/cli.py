"""Interfaz de linea de comandos del agente A4-ECEF.

Un solo verbo: `evaluar`. No hay comando que emita balance ni concepto. La
salida termina siempre en PENDIENTE_DE_LECTURA_HUMANA.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ...aplicacion.evaluar_evidencia import evaluar_evidencia
from ...config import ahora, construir_dependencias
from ...domain.errores import SalidaConclusivaError
from ...domain.modelos import Hallazgo, Severidad

app = typer.Typer(
    add_completion=False,
    help="Agente A4-ECEF: auditoria de evidencia cientifica (Modulos 4, 5 y 7).",
)
consola = Console()

_COLOR_SEVERIDAD = {
    Severidad.CRITICA: "bold red",
    Severidad.ALTA: "red",
    Severidad.MEDIA: "yellow",
    Severidad.BAJA: "cyan",
    Severidad.INFORMATIVA: "dim",
}


def _tabla_hallazgos(hallazgos: tuple[Hallazgo, ...], limite: int) -> Table:
    tabla = Table(
        title=f"Hallazgos ({min(limite, len(hallazgos))} de {len(hallazgos)})",
        title_justify="left",
    )
    tabla.add_column("Severidad", style="bold")
    tabla.add_column("Parametro")
    tabla.add_column("Clase")
    for hallazgo in hallazgos[:limite]:
        color = _COLOR_SEVERIDAD[hallazgo.severidad]
        tabla.add_row(
            f"[{color}]{hallazgo.severidad}[/{color}]",
            hallazgo.parametro,
            str(hallazgo.clase),
        )
    return tabla


@app.command()
def evaluar(
    evidencia: Annotated[
        Path,
        typer.Argument(help="Ruta a los Modulos 4, 5 y 7 en Markdown del expediente."),
    ],
    radicado: Annotated[
        str, typer.Option(help="Numero de radicado del tramite.")
    ] = "SIN-RADICADO",
    salida: Annotated[
        Path | None, typer.Option(help="Archivo donde escribir el payload JSON.")
    ] = None,
    detalle: Annotated[
        int, typer.Option(help="Cuantos hallazgos mostrar en consola.")
    ] = 12,
) -> None:
    """Audita la evidencia cientifica y deja el resultado listo para lectura humana."""
    dependencias = construir_dependencias(evidencia)
    try:
        resultado = evaluar_evidencia(
            radicado=radicado,
            lector=dependencias.lector,
            auditoria=dependencias.auditoria,
            momento=ahora(),
        )
    except SalidaConclusivaError as error:
        consola.print(
            Panel(str(error), title="Guardia lexica: corrida abortada", border_style="red")
        )
        raise typer.Exit(code=2) from error

    consola.print(
        Panel(
            resultado.payload["aviso_de_alcance"],
            title=f"A4-ECEF - radicado {radicado}",
            border_style="blue",
        )
    )
    consola.print(_tabla_hallazgos(resultado.hallazgos, detalle))

    preguntas = resultado.payload["insumos_para_el_balance"][
        "preguntas_abiertas_para_el_evaluador"
    ]
    if preguntas:
        consola.print("\n[bold]Preguntas abiertas para el evaluador[/bold]")
        for pregunta in preguntas:
            consola.print(f"  - {pregunta}")

    destino = salida or Path(f"evidencia_cientifica_{radicado}.json")
    destino.write_text(
        json.dumps(resultado.payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    consola.print(f"\nPayload escrito en {destino}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
