"""CLI command: openquery sources — list all available data sources."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

console = Console()


def sources_cmd() -> None:
    """List all available data sources."""
    from openquery.sources import list_sources

    sources = list_sources()

    table = Table(title="Available Data Sources", show_lines=True)
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Country", style="green", no_wrap=True)
    table.add_column("Description")
    table.add_column("Inputs", style="yellow")
    table.add_column("Captcha", style="red", no_wrap=True)

    for src in sources:
        meta = src.meta()
        inputs = ", ".join(meta.supported_inputs)
        captcha = "Yes" if meta.requires_captcha else "No"
        table.add_row(meta.name, meta.country, meta.display_name, inputs, captcha)

    console.print(table)
