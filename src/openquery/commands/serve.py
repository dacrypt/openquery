"""CLI command: openquery serve — start the FastAPI server."""

from __future__ import annotations

import typer
from rich.console import Console

console = Console()


def serve_cmd(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Bind address"),
    port: int = typer.Option(8000, "--port", "-p", help="Port number"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload"),
) -> None:
    """Start the OpenQuery API server."""
    try:
        import uvicorn
    except ImportError:
        console.print(
            "[red]Error:[/red] FastAPI/uvicorn not installed. "
            "Install: pip install 'openquery[serve]'"
        )
        raise typer.Exit(1)

    console.print(f"[bold]Starting OpenQuery API server on {host}:{port}[/bold]")
    console.print(f"  Docs: http://{host}:{port}/docs")
    console.print(f"  Sources: http://{host}:{port}/api/v1/sources")

    uvicorn.run(
        "openquery.server.app:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
    )
