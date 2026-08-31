"""Interfaz de linea de comandos del agente A3-ECPF.

Un solo verbo: `auditar`. No hay un comando que cierre el expediente ni que
emita concepto, igual que en el A1 no hay bandera que enrute sin persona. La
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

from ...aplicacion.auditar_calidad import auditar_calidad
from ...config import ahora, construir_dependencias
from ...domain.errores import SalidaConclusivaError
from ...domain.modelos import Hallazgo, Severidad

app = typer.Typer(
    add_completion=False,
    help="Agente A3-ECPF: auditoria de calidad y procesos del Modulo 3 (CMC).",
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
        show_lines=False,
    )
    tabla.add_column("Severidad", style="bold")
    tabla.add_column("Parametro")
    tabla.add_column("Clase")
    tabla.add_column("Folio")
    for hallazgo in hallazgos[:limite]:
        traza = hallazgo.medicion.valor.traza if hallazgo.medicion else None
        folio = str(traza.pagina) if traza and traza.pagina else "-"
        color = _COLOR_SEVERIDAD[hallazgo.severidad]
        tabla.add_row(
            f"[{color}]{hallazgo.severidad}[/{color}]",
            hallazgo.parametro,
            str(hallazgo.clase),
            folio,
        )
    return tabla


@app.command()
def auditar(
    modulo3: Annotated[
        Path,
        typer.Argument(help="Ruta al Modulo 3 en Markdown del expediente."),
    ],
    radicado: Annotated[
        str, typer.Option(help="Numero de radicado del tramite.")
    ] = "SIN-RADICADO",
    salida: Annotated[
        Path | None,
        typer.Option(help="Archivo donde escribir el payload JSON."),
    ] = None,
    detalle: Annotated[
        int, typer.Option(help="Cuantos hallazgos mostrar en consola.")
    ] = 12,
) -> None:
    """Audita el Modulo 3 y deja el resultado listo para lectura humana."""
    dependencias = construir_dependencias(modulo3)
    try:
        resultado = auditar_calidad(
            radicado=radicado,
            lector=dependencias.lector,
            auditoria=dependencias.auditoria,
            especificaciones_normativas=dependencias.especificaciones,
            momento=ahora(),
        )
    except SalidaConclusivaError as error:
        consola.print(
            Panel(
                str(error),
                title="Guardia lexica: corrida abortada",
                border_style="red",
            )
        )
        raise typer.Exit(code=2) from error

    resumen = resultado.payload["resumen"]
    consola.print(
        Panel(
            resultado.payload["aviso_de_alcance"],
            title=f"A3-ECPF - radicado {radicado}",
            border_style="blue",
        )
    )
    consola.print(_tabla_hallazgos(resultado.hallazgos, detalle))
    consola.print(
        f"Cobertura verificable: "
        f"{resumen['cobertura_verificable']['valor']}% de los hallazgos se "
        f"contrastaron contra un limite declarado en el expediente."
    )
    if resumen["parametros_sin_especificacion_declarada"]:
        consola.print(
            "Sin especificacion declarada: "
            + ", ".join(resumen["parametros_sin_especificacion_declarada"])
        )

    destino = salida or Path(f"auditoria_calidad_{radicado}.json")
    destino.write_text(
        json.dumps(resultado.payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    consola.print(f"Payload escrito en {destino}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
