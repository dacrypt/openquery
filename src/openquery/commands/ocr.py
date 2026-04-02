"""CLI command: openquery ocr — extract data from ID document images."""

from __future__ import annotations

import json
import sys

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def ocr_cmd(
    image: str = typer.Argument(..., help="Path to the document image"),
    doc_type: str = typer.Option(
        ..., "--type", "-t",
        help="Document type: co.cedula, mx.ine, pe.dni, cl.carnet, passport.mrz",
    ),
    output_json: bool = typer.Option(False, "--json", "-j", help="Output raw JSON"),
) -> None:
    """Extract structured data from an ID document image."""
    from pathlib import Path

    from openquery.core.document_ocr import DocumentOCR
    from openquery.models.ocr import DocumentTypeOCR

    image_path = Path(image)
    if not image_path.exists():
        console.print(f"[red]Error:[/red] File not found: {image}")
        raise typer.Exit(1)

    try:
        dtype = DocumentTypeOCR(doc_type)
    except ValueError:
        valid = ", ".join(t.value for t in DocumentTypeOCR)
        console.print(f"[red]Error:[/red] Invalid document type '{doc_type}'. Valid: {valid}")
        raise typer.Exit(1)

    try:
        ocr = DocumentOCR()
        result = ocr.extract_from_path(str(image_path), dtype)
    except ImportError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] OCR extraction failed: {e}")
        raise typer.Exit(1)

    if output_json:
        console.print(result.model_dump_json(indent=2))
        return

    # Rich output
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Field")
    table.add_column("Value", style="green")

    for field, value in result.fields.items():
        table.add_row(field, value)

    panel = Panel(
        table,
        title=f"[bold]OCR: {doc_type}[/bold]",
        subtitle=f"Confidence: {result.confidence:.1%} | {result.processing_time_ms}ms",
    )
    console.print(panel)
