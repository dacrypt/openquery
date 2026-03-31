"""CLI command: openquery query <source> --cedula/--placa/--vin <value>"""

from __future__ import annotations

import time

import typer
from rich.console import Console
from rich.panel import Panel

from openquery.sources.base import DocumentType, QueryInput

console = Console()


def query_cmd(
    source: str = typer.Argument(help="Source name, e.g. co.simit, co.runt"),
    cedula: str | None = typer.Option(None, "--cedula", "-c", help="Cedula number"),
    placa: str | None = typer.Option(None, "--placa", "-p", help="License plate"),
    vin: str | None = typer.Option(None, "--vin", "-v", help="VIN number"),
    output_json: bool = typer.Option(False, "--json", "-j", help="Output raw JSON"),
) -> None:
    """Query a public data source."""
    from openquery.sources import get_source

    # Determine document type and number
    if cedula:
        doc_type = DocumentType.CEDULA
        doc_number = cedula
    elif placa:
        doc_type = DocumentType.PLATE
        doc_number = placa
    elif vin:
        doc_type = DocumentType.VIN
        doc_number = vin
    else:
        console.print("[red]Error:[/red] Provide --cedula, --placa, or --vin")
        raise typer.Exit(1)

    try:
        src = get_source(source)
    except KeyError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e

    meta = src.meta()
    if not src.supports(doc_type):
        supported = ", ".join(meta.supported_inputs)
        console.print(
            f"[red]Error:[/red] Source '{source}' does not support '{doc_type}'. "
            f"Supported: {supported}"
        )
        raise typer.Exit(1)

    console.print(f"[bold]Querying {meta.display_name}...[/bold]")

    start = time.monotonic()
    try:
        result = src.query(QueryInput(document_type=doc_type, document_number=doc_number))
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e
    elapsed_ms = int((time.monotonic() - start) * 1000)

    if output_json:
        console.print(result.model_dump_json(indent=2))
    else:
        data = result.model_dump()
        # Pretty print with Rich
        lines = []
        for key, value in data.items():
            if key == "queried_at":
                continue
            if isinstance(value, list) and len(value) > 3:
                lines.append(f"[cyan]{key}:[/cyan] ({len(value)} items)")
            elif value or value == 0:
                lines.append(f"[cyan]{key}:[/cyan] {value}")
        console.print(Panel(
            "\n".join(lines),
            title=f"{meta.display_name} — {doc_number}",
            subtitle=f"{elapsed_ms}ms",
        ))
