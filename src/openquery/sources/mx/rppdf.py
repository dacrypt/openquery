"""RPPDF source — CDMX property registry (Mexico).

Queries the Registro Publico de la Propiedad del Distrito Federal
for property ownership data.

Flow:
1. Navigate to RPPDF consultation page
2. Enter folio number
3. Parse result for owner, property type

Source: https://www.sedatu.gob.mx/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.mx.rppdf import RppdfResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

RPPDF_URL = "https://www.rppdf.cdmx.gob.mx/portal/consultas"


@register
class RppdfSource(BaseSource):
    """Query CDMX property registry (RPPDF)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="mx.rppdf",
            display_name="RPPDF — Registro Publico de la Propiedad CDMX",
            description="CDMX property registry — folio-based ownership data (Mexico)",
            country="MX",
            url=RPPDF_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        folio = input.extra.get("folio") or input.document_number
        if not folio:
            raise SourceError("mx.rppdf", "folio is required")
        return self._query(folio, audit=input.audit)

    def _query(self, folio: str, audit: bool = False) -> RppdfResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("mx.rppdf", "custom", folio)

        with browser.page(RPPDF_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                folio_input = page.query_selector(
                    'input[type="text"], input[id*="folio"], '
                    'input[id*="numero"], input[id*="consulta"]'
                )
                if not folio_input:
                    raise SourceError("mx.rppdf", "Could not find folio input field")

                folio_input.fill(folio)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="buscar"], button[id*="consultar"]'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    folio_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, folio)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("mx.rppdf", f"Query failed: {e}") from e

    def _parse_result(self, page, folio: str) -> RppdfResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        owner = ""
        property_type = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if not stripped:
                continue
            if ("propietario" in lower or "titular" in lower or "nombre" in lower) and ":" in stripped:  # noqa: E501
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not owner:
                    owner = parts[1].strip()
            elif ("tipo" in lower or "clase" in lower or "inmueble" in lower) and ":" in stripped:
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not property_type:
                    property_type = parts[1].strip()

        return RppdfResult(
            queried_at=datetime.now(),
            folio=folio,
            owner=owner,
            property_type=property_type,
            details={"queried": True},
        )
