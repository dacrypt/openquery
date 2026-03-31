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
    audit: bool = typer.Option(False, "--audit", "-a", help="Capture evidence (screenshots + PDF)"),
    audit_dir: str | None = typer.Option(None, "--audit-dir", help="Directory to save audit files"),
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
    if audit:
        console.print("[dim]Audit mode: capturing evidence...[/dim]")

    start = time.monotonic()
    try:
        result = src.query(QueryInput(
            document_type=doc_type, document_number=doc_number, audit=audit,
        ))
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

    # Save audit files if requested
    if audit and hasattr(result, "audit") and result.audit is not None:
        _save_audit(result.audit, source, doc_number, audit_dir)


def _save_audit(audit_record, source: str, doc_number: str, audit_dir: str | None) -> None:
    """Save audit evidence to disk."""
    import base64
    import json
    from pathlib import Path

    from openquery.models.audit import AuditRecord

    out_dir = Path(audit_dir) if audit_dir else Path.cwd() / "audit"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Filename prefix: source_masked-doc_timestamp
    masked = AuditRecord.mask_document(doc_number)
    ts = audit_record.queried_at.strftime("%Y%m%d_%H%M%S")
    prefix = f"{source}_{masked}_{ts}"

    # Save PDF
    if audit_record.pdf_base64:
        pdf_path = out_dir / f"{prefix}_evidence.pdf"
        pdf_path.write_bytes(base64.b64decode(audit_record.pdf_base64))
        console.print(f"[green]PDF saved:[/green] {pdf_path}")

    # Save screenshots
    for ss in audit_record.screenshots:
        if ss.png_base64:
            ss_path = out_dir / f"{prefix}_{ss.label}.png"
            ss_path.write_bytes(base64.b64decode(ss.png_base64))
            console.print(f"[green]Screenshot saved:[/green] {ss_path}")

    # Save audit metadata as JSON (without base64 blobs)
    meta_record = audit_record.model_dump(mode="json")
    meta_record.pop("pdf_base64", None)
    for ss in meta_record.get("screenshots", []):
        ss.pop("png_base64", None)
    meta_path = out_dir / f"{prefix}_audit.json"
    meta_path.write_text(json.dumps(meta_record, indent=2, ensure_ascii=False))
    console.print(f"[green]Audit log saved:[/green] {meta_path}")
