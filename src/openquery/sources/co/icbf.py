"""ICBF source — Colombian child welfare checks.

Queries the ICBF (Instituto Colombiano de Bienestar Familiar) for
child welfare and family records.

Source: https://www.icbf.gov.co/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.icbf import IcbfResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

ICBF_URL = "https://www.icbf.gov.co/"


@register
class IcbfSource(BaseSource):
    """Query ICBF child welfare records."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.icbf",
            display_name="ICBF — Bienestar Familiar",
            description="ICBF child welfare and family records lookup",
            country="CO",
            url=ICBF_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (
            input.extra.get("name", "")
            or input.document_number
        ).strip()
        if not search_term:
            raise SourceError("co.icbf", "Name required (pass via extra.name or document_number)")
        return self._query(search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> IcbfResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.icbf", "name", search_term)

        with browser.page(ICBF_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(2000)

                search_input = page.locator(
                    'input[type="search"], input[placeholder*="buscar"], '
                    'input[placeholder*="Buscar"], input[type="text"]'
                ).first
                if search_input:
                    search_input.fill(search_term)
                    logger.info("Searching ICBF for: %s", search_term)
                    search_input.press("Enter")
                    page.wait_for_timeout(3000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_term)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("co.icbf", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> IcbfResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = IcbfResult(queried_at=datetime.now(), search_term=search_term)

        lines = [ln.strip() for ln in body_text.split("\n") if ln.strip()]
        result.total_records = len([ln for ln in lines if search_term.lower() in ln.lower()])

        return result
