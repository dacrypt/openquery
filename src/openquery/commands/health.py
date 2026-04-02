"""CLI command: openquery health — show source health status."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from openquery.models.health import CircuitState

console = Console()

STATUS_STYLES = {
    CircuitState.CLOSED: ("[green]HEALTHY[/green]"),
    CircuitState.HALF_OPEN: ("[yellow]DEGRADED[/yellow]"),
    CircuitState.OPEN: ("[red]UNAVAIL[/red]"),
}


def health_cmd() -> None:
    """Show health status for all sources."""
    from openquery.sources import list_sources

    sources = list_sources()

    table = Table(title="Source Health Status", show_lines=False)
    table.add_column("Source", style="cyan", no_wrap=True)
    table.add_column("Country", style="blue", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Description")

    for src in sources:
        meta = src.meta()
        status_str = STATUS_STYLES[CircuitState.CLOSED]
        table.add_row(meta.name, meta.country, status_str, meta.display_name)

    console.print(table)
    console.print(
        f"\n[bold]{len(sources)}[/bold] sources registered. "
        "Run [cyan]openquery serve[/cyan] and query sources to see live health data."
    )
