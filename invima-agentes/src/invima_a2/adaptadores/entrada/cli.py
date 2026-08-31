"""CLI del Agente A2-VICR."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ...aplicacion.validar_y_clasificar import (
    ResultadoDictamen,
    ValidarYClasificarUseCase,
)
from ...config import Ajustes, construir_dependencias
from ...domain.errores import ExpedienteNoValidableError
from ...domain.estados import EstadoDictamen

consola = Console()

app = typer.Typer(
    add_completion=False,
    help="A2-VICR: valida el Modulo 1 y clasifica el producto. No reparte expedientes.",
)

_COLOR_SEVERIDAD = {
    "CRITICA": "bold red",
    "ALTA": "yellow",
    "MEDIA": "cyan",
    "INFORMATIVA": "dim",
}


def _tabla_alertas(alertas: list[dict]) -> Table:
    tabla = Table(title="Alertas", show_lines=False)
    tabla.add_column("Severidad", no_wrap=True)
    tabla.add_column("Hallazgo")
    tabla.add_column("Esperado / Encontrado")
    for alerta in alertas:
        sev = alerta["severidad"]
        tabla.add_row(
            f"[{_COLOR_SEVERIDAD.get(sev, 'white')}]{sev}[/]",
            alerta["mensaje"],
            f"{alerta['esperado']}\n[dim]{alerta['encontrado']}[/dim]",
        )
    return tabla


def _mostrar(resultado: ResultadoDictamen) -> None:
    payload = resultado.payload
    clasificacion = payload["clasificacion_taxonomica"]

    tabla = Table(title="Clasificacion taxonomica", show_header=False)
    tabla.add_column("Campo", style="bold")
    tabla.add_column("Valor")
    for etiqueta, clave in (
        ("Dimension", "dimension_producto"),
        ("Ruta de estudio", "ruta_estudio"),
        ("Marco normativo", "marco_normativo"),
    ):
        bloque = clasificacion[clave]
        tabla.add_row(etiqueta, f"{bloque['valor']}  [dim]({bloque['origen']})[/dim]")
    consola.print(tabla)

    alertas = payload["alertas"]
    if alertas:
        consola.print(_tabla_alertas(alertas))
    else:
        consola.print("[green]Sin hallazgos en la documentacion legal del Modulo 1[/green]")

    heredado = payload["heredado_del_a1"]
    if heredado.get("enrutamiento_recomendado"):
        ruta = heredado["enrutamiento_recomendado"]["ruta_recomendada"]["valor"]
        consola.print(f"\nRuta recomendada por el A1: [bold]{ruta}[/bold]")

    if resultado.retenido:
        consola.print(
            Panel(
                "Hay al menos un hallazgo CRITICO. El agente NO recomienda repartir "
                "el expediente a los grupos evaluadores.\n\n"
                "Esto no es un rechazo: el agente no rechaza ni devuelve tramites. "
                "Retiene la recomendacion y pone los hallazgos a la vista. Levantar "
                "la retencion es decision del Coordinador de Grupos, y queda firmada "
                "(art. 7.1, Resolucion 2026025611).",
                title="Reparto retenido",
                border_style="red",
            )
        )
    else:
        consola.print(
            Panel(
                "El dictamen queda a la espera del Coordinador de Grupos. El agente "
                "clasifica y recomienda; el reparto a los grupos evaluadores es una "
                "decision administrativa con nombre propio.",
                title="Pendiente de validacion",
                border_style="blue",
            )
        )


@app.command()
def dictaminar(
    radicado: Annotated[str, typer.Argument(help="Radicado ya procesado por el A1")],
    dossier: Annotated[
        Path | None, typer.Option(help="Carpeta de folios, si no es la registrada")
    ] = None,
    offline: Annotated[bool, typer.Option(help="Sin red ni consumo de credito")] = True,
    modelo: Annotated[str, typer.Option(help="Modelo a usar si no es offline")] = "",
    salida: Annotated[Path | None, typer.Option(help="Ruta del dictamen JSON")] = None,
    json_only: Annotated[bool, typer.Option("--json", help="Solo imprimir el JSON")] = False,
) -> None:
    """Valida el Modulo 1 y clasifica el producto de un expediente del A1."""
    ajustes = Ajustes.desde_entorno(offline=offline, modelo=modelo or None)
    deps, fuente = construir_dependencias(ajustes)
    if dossier is not None:
        fuente.registrar_carpeta(radicado, dossier)

    try:
        resultado = ValidarYClasificarUseCase(deps).ejecutar(radicado)
    except ExpedienteNoValidableError as error:
        consola.print(Panel(str(error), title="Expediente no validable", border_style="yellow"))
        raise typer.Exit(code=2)
    except KeyError as error:
        consola.print(Panel(str(error), title="Radicado desconocido", border_style="red"))
        raise typer.Exit(code=2)

    if json_only:
        print(json.dumps(resultado.payload, ensure_ascii=False, indent=2))
    else:
        _mostrar(resultado)

    if salida is not None:
        salida.write_text(
            json.dumps(resultado.payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        consola.print(f"\nDictamen escrito en {salida}")


@app.command()
def estados() -> None:
    """Imprime la maquina de estados del dictamen y sus barreras."""
    tabla = Table(title="Transiciones del dictamen del A2")
    tabla.add_column("Origen")
    tabla.add_column("Automatica")
    tabla.add_column("Requiere Coordinador")

    from ...domain.estados import (
        TRANSICIONES_AUTOMATICAS,
        TRANSICIONES_CON_DECISION_HUMANA,
    )

    for estado in EstadoDictamen:
        automaticas = TRANSICIONES_AUTOMATICAS.get(estado, frozenset())
        humanas = TRANSICIONES_CON_DECISION_HUMANA.get(estado, frozenset())
        tabla.add_row(
            str(estado),
            ", ".join(sorted(str(e) for e in automaticas)) or "[dim]ninguna[/dim]",
            ", ".join(sorted(str(e) for e in humanas)) or "[dim]ninguna[/dim]",
        )
    consola.print(tabla)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
