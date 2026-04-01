"""Migración PPT source — Permiso por Protección Temporal.

Queries Migración Colombia for PPT (Permiso por Protección Temporal)
status, used by Venezuelan nationals under temporary protection.

Flow:
1. Navigate to Migración Colombia consultation page
2. Enter PPT document number
3. Submit and parse PPT status

Source: https://www.migracioncolombia.gov.co/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.migracion_ppt import MigracionPptResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

MIGRACION_URL = "https://www.migracioncolombia.gov.co/"


@register
class MigracionPptSource(BaseSource):
    """Query Colombian PPT (Permiso por Protección Temporal) status."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.migracion_ppt",
            display_name="Migración — Permiso por Protección Temporal",
            description="Colombian PPT (Permiso por Protección Temporal) status check",
            country="CO",
            url=MIGRACION_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CUSTOM:
            raise SourceError(
                "co.migracion_ppt",
                f"Only CUSTOM document type supported for PPT, got: {input.document_type}",
            )
        return self._query(input.document_number, audit=input.audit)

    def _query(self, documento: str, audit: bool = False) -> MigracionPptResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.migracion_ppt", "custom", documento)

        with browser.page(MIGRACION_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_selector('input[type="text"], input[type="search"]', timeout=15000)
                page.wait_for_timeout(2000)

                # Look for PPT consultation section or search input
                doc_input = page.query_selector(
                    'input[type="text"][id*="ppt"], '
                    'input[type="text"][id*="documento"], '
                    'input[type="text"][id*="numero"], '
                    'input[type="text"][id*="consulta"], '
                    'input[type="text"]'
                )
                if not doc_input:
                    raise SourceError("co.migracion_ppt", "Could not find document input field")

                doc_input.fill(documento)
                logger.info("Searching PPT for: %s", documento)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="consultar"], button[id*="buscar"], '
                    'a[id*="consultar"]'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    doc_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, documento)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("co.migracion_ppt", f"Query failed: {e}") from e

    def _parse_result(self, page, documento: str) -> MigracionPptResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        result = MigracionPptResult(
            queried_at=datetime.now(),
            documento=documento,
        )

        # Detect PPT status keywords
        if "vigente" in body_lower:
            result.tiene_ppt = True
            result.estado_ppt = "Vigente"
        elif "vencido" in body_lower:
            result.tiene_ppt = True
            result.estado_ppt = "Vencido"
        elif "en trámite" in body_lower or "en tramite" in body_lower:
            result.tiene_ppt = True
            result.estado_ppt = "En trámite"
        elif any(phrase in body_lower for phrase in [
            "no registra", "no se encontr", "sin registro",
        ]):
            result.tiene_ppt = False
            result.estado_ppt = "No registra"

        # Try to extract name
        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if "nombre" in lower and ":" in stripped:
                result.nombre = stripped.split(":", 1)[1].strip()
                break

        # Try to extract dates
        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if "expedición" in lower or "expedicion" in lower:
                if ":" in stripped:
                    result.fecha_expedicion = stripped.split(":", 1)[1].strip()
            elif "vencimiento" in lower:
                if ":" in stripped:
                    result.fecha_vencimiento = stripped.split(":", 1)[1].strip()

        if result.tiene_ppt:
            result.mensaje = f"PPT {result.estado_ppt} para documento {documento}"
        else:
            result.mensaje = f"No se encontró PPT para documento {documento}"

        return result
