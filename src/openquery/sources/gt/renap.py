"""Guatemala RENAP source — DPI identity / processing status.

Queries Guatemala's RENAP (Registro Nacional de las Personas) for
DPI processing status and identity information.

Flow:
1. Navigate to RENAP DPI status page
2. Enter DPI or application number
3. Submit and parse status, identity info

Source: https://www.renap.gob.gt/estado-tramite-dpi
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.gt.renap import GtRenapResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

RENAP_URL = "https://www.renap.gob.gt/estado-tramite-dpi"


@register
class GtRenapSource(BaseSource):
    """Query Guatemala RENAP for DPI processing status and identity info."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="gt.renap",
            display_name="RENAP — Estado de Trámite DPI",
            description="Guatemala DPI processing status and identity info (RENAP)",
            country="GT",
            url=RENAP_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CEDULA:
            raise SourceError(
                "gt.renap", f"Only cedula (DPI) supported, got: {input.document_type}"
            )
        dpi = input.document_number.strip()
        if not dpi:
            raise SourceError("gt.renap", "DPI or application number is required")
        return self._query(dpi, audit=input.audit)

    def _query(self, dpi: str, audit: bool = False) -> GtRenapResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("gt.renap", "dpi", dpi)

        with browser.page(RENAP_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill DPI / application number input
                dpi_input = page.query_selector(
                    'input[id*="dpi"], input[name*="dpi"], '
                    'input[id*="DPI"], input[name*="DPI"], '
                    'input[id*="cui"], input[name*="cui"], '
                    'input[id*="tramite"], input[name*="tramite"], '
                    'input[type="text"]'
                )
                if not dpi_input:
                    raise SourceError("gt.renap", "Could not find DPI input field")

                dpi_input.fill(dpi)
                logger.info("Filled DPI: %s", dpi)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="consultar"], button[id*="buscar"], '
                    'button:has-text("Consultar"), button:has-text("Buscar")'
                )
                if submit:
                    submit.click()
                else:
                    dpi_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, dpi)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("gt.renap", f"Query failed: {e}") from e

    def _parse_result(self, page, dpi: str) -> GtRenapResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = GtRenapResult(queried_at=datetime.now(), dpi=dpi)
        details: dict[str, str] = {}

        lower = body_text.lower()

        field_map = {
            "nombre": "nombre",
            "estado": "status",
            "estatus": "status",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            lower_line = stripped.lower()
            for label, attr in field_map.items():
                if label in lower_line and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value:
                        setattr(result, attr, value)
                    break
            # Collect all key:value pairs into details
            if ":" in stripped:
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip()
                if key and val:
                    details[key] = val

        # Detect status keywords — overrides field_map for known states
        if "entregado" in lower or "listo" in lower:
            result.status = "Entregado"
        elif "en proceso" in lower or "proceso" in lower:
            result.status = "En Proceso"
        elif "pendiente" in lower:
            result.status = "Pendiente"
        elif "rechazado" in lower:
            result.status = "Rechazado"

        result.details = details
        return result
