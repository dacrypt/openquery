"""CNV source — Argentina securities regulator lookup.

Queries Argentina's CNV for registered entities by company name.

Flow:
1. Navigate to the CNV portal
2. Enter company name
3. Submit and parse registration status

Source: https://www.cnv.gov.ar/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ar.cnv import CnvResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CNV_URL = "https://www.cnv.gov.ar/"


@register
class CnvSource(BaseSource):
    """Query Argentina's CNV securities regulator for registered entities."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ar.cnv",
            display_name="CNV — Comisión Nacional de Valores",
            description="Argentina securities regulator: registered entities and status by company name",  # noqa: E501
            country="AR",
            url=CNV_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CUSTOM:
            raise SourceError("ar.cnv", f"Unsupported input type: {input.document_type}")

        search_term = input.extra.get("company", "").strip()
        if not search_term:
            raise SourceError("ar.cnv", "Must provide extra['company'] (company name)")

        return self._query(search_term=search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> CnvResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("ar.cnv", "empresa", search_term)

        with browser.page(CNV_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[id*="denominaci"], input[name*="denominaci"], '
                    'input[id*="empresa"], input[name*="empresa"], '
                    'input[placeholder*="denominaci" i], input[type="search"], '
                    'input[type="text"]'
                )
                if search_input:
                    search_input.fill(search_term)
                    logger.info("Filled company name: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button:has-text("Buscar"), button:has-text("Consultar")'
                )
                if submit:
                    submit.click()
                else:
                    page.keyboard.press("Enter")

                page.wait_for_timeout(4000)
                page.wait_for_selector("body", timeout=15000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_term)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("ar.cnv", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> CnvResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = CnvResult(queried_at=datetime.now(), search_term=search_term)
        details: dict = {}

        rows = page.query_selector_all("table tr, .result tr")
        for row in rows:
            cells = row.query_selector_all("td, th")
            if len(cells) >= 2:
                label = (cells[0].inner_text() or "").strip()
                value = (cells[1].inner_text() or "").strip()
                if label and value:
                    details[label] = value
                    label_lower = label.lower()
                    if "denominaci" in label_lower or "nombre" in label_lower or "raz" in label_lower:  # noqa: E501
                        result.entity_name = value
                    elif "registr" in label_lower or "estado" in label_lower or "habilitaci" in label_lower:  # noqa: E501
                        result.registration_status = value

        if details:
            result.details = details

        # Fallback: body text scan
        if not result.entity_name:
            for line in body_text.split("\n"):
                stripped = line.strip()
                lower = stripped.lower()
                if ("denominaci" in lower or "nombre" in lower) and ":" in stripped:
                    result.entity_name = stripped.split(":", 1)[1].strip()
                elif (
                    ("registr" in lower or "estado" in lower)
                    and ":" in stripped
                    and not result.registration_status
                ):
                    result.registration_status = stripped.split(":", 1)[1].strip()

        return result
