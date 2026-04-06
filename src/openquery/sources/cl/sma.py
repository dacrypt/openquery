"""SMA source — Chile environmental sanctions lookup.

Queries Chile's SMA SNIFA for environmental sanctions by company name or RUT.

Flow:
1. Navigate to the SNIFA portal
2. Enter company name or RUT
3. Submit and parse sanction records

Source: https://snifa.sma.gob.cl/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.cl.sma import SmaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SMA_URL = "https://snifa.sma.gob.cl/"


@register
class SmaSource(BaseSource):
    """Query Chile's SMA SNIFA environmental sanctions portal."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="cl.sma",
            display_name="SMA — Superintendencia del Medio Ambiente",
            description="Chile environmental sanctions: total sanctions and details by company name or RUT",  # noqa: E501
            country="CL",
            url=SMA_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CUSTOM:
            raise SourceError("cl.sma", f"Unsupported input type: {input.document_type}")

        search_term = input.extra.get("company", "").strip()
        if not search_term:
            raise SourceError("cl.sma", "Must provide extra['company'] (company name or RUT)")

        return self._query(search_term=search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> SmaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("cl.sma", "empresa", search_term)

        with browser.page(SMA_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[id*="empresa"], input[name*="empresa"], '
                    'input[id*="rut"], input[name*="rut"], '
                    'input[placeholder*="empresa" i], input[type="search"], '
                    'input[type="text"]'
                )
                if search_input:
                    search_input.fill(search_term)
                    logger.info("Filled search term: %s", search_term)

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
                raise SourceError("cl.sma", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> SmaResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = SmaResult(queried_at=datetime.now(), search_term=search_term)
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
                    if "empresa" in label_lower or "nombre" in label_lower or "raz" in label_lower:
                        result.company_name = value
                    elif "sanci" in label_lower or "total" in label_lower or "infracci" in label_lower:  # noqa: E501
                        result.total_sanctions = value

        if details:
            result.details = details

        # Fallback: body text scan
        if not result.total_sanctions:
            for line in body_text.split("\n"):
                stripped = line.strip()
                lower = stripped.lower()
                if ("empresa" in lower or "raz" in lower) and ":" in stripped and not result.company_name:  # noqa: E501
                    result.company_name = stripped.split(":", 1)[1].strip()
                elif (
                    ("sanci" in lower or "total" in lower or "infracci" in lower)
                    and ":" in stripped
                    and not result.total_sanctions
                ):
                    result.total_sanctions = stripped.split(":", 1)[1].strip()

        return result
