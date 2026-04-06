"""OpenQuery CLI entry point."""

from __future__ import annotations

import typer

from openquery import __version__

app = typer.Typer(
    name="openquery",
    help="Query public data sources worldwide.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"openquery {__version__}")
        raise typer.Exit()


@app.callback()
def main_callback(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """OpenQuery — Query public data sources worldwide."""


# Register sub-commands
from openquery.commands.face import face_verify_cmd  # noqa: E402
from openquery.commands.health import health_cmd  # noqa: E402
from openquery.commands.ocr import ocr_cmd  # noqa: E402
from openquery.commands.query import query_cmd  # noqa: E402
from openquery.commands.serve import serve_cmd  # noqa: E402
from openquery.commands.sources import sources_cmd  # noqa: E402

app.command("query")(query_cmd)
app.command("sources")(sources_cmd)
app.command("serve")(serve_cmd)
app.command("health")(health_cmd)
app.command("ocr")(ocr_cmd)
app.command("face-verify")(face_verify_cmd)


def main() -> None:
    app()
