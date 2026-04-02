"""CLI command: openquery face-verify — compare two face images."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel

console = Console()


def face_verify_cmd(
    image1: str = typer.Argument(..., help="Path to the first face image (e.g., ID photo)"),
    image2: str = typer.Argument(..., help="Path to the second face image (e.g., selfie)"),
    model: str = typer.Option("ArcFace", "--model", "-m", help="Face model: ArcFace, Facenet, VGG-Face"),
    output_json: bool = typer.Option(False, "--json", "-j", help="Output raw JSON"),
) -> None:
    """Verify identity by comparing two face images."""
    from pathlib import Path

    from openquery.core.face import FaceVerifier

    for path_str, label in [(image1, "Image 1"), (image2, "Image 2")]:
        if not Path(path_str).exists():
            console.print(f"[red]Error:[/red] {label} not found: {path_str}")
            raise typer.Exit(1)

    try:
        verifier = FaceVerifier(model_name=model)
        result = verifier.verify_from_paths(image1, image2)
    except ImportError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] Face verification failed: {e}")
        raise typer.Exit(1)

    if output_json:
        console.print(result.model_dump_json(indent=2))
        return

    # Rich output
    verified_str = "[bold green]MATCH[/bold green]" if result.verified else "[bold red]NO MATCH[/bold red]"
    liveness_str = "[green]REAL[/green]" if result.liveness else "[red]SPOOF[/red]"

    content = (
        f"Result:      {verified_str}\n"
        f"Confidence:  {result.confidence:.1%}\n"
        f"Distance:    {result.distance:.4f} (threshold: {result.threshold:.4f})\n"
        f"Liveness:    {liveness_str}\n"
        f"Model:       {result.model}\n"
        f"Time:        {result.processing_time_ms}ms"
    )

    panel = Panel(content, title="[bold]Face Verification[/bold]")
    console.print(panel)
