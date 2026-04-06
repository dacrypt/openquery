"""PROCOMER source — Costa Rica export/trade data.

Queries PROCOMER (Promotora del Comercio Exterior de Costa Rica)
for export statistics and trade data by product or company.
Browser-based, no CAPTCHA.

URL: https://www.procomer.com/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.cr.procomer import CrProcomerResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

PROCOMER_URL = "https://www.procomer.com/"


@register
class CrProcomerSource(BaseSource):
    """Query Costa Rica PROCOMER export/trade statistics."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="cr.procomer",
            display_name="PROCOMER — Comercio Exterior (CR)",
            description="Costa Rica PROCOMER export and trade statistics by product or company",
            country="CR",
            url=PROCOMER_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("search_term", "") or input.document_number
        if not search_term:
            raise SourceError("cr.procomer", "Search term is required")
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> CrProcomerResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("cr.procomer", "search_term", search_term)

        with browser.page(PROCOMER_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "page_loaded")

                search_input = page.query_selector(
                    "input[name*='search'], input[name*='buscar'], input[name*='q'], "
                    "input[id*='search'], input[id*='buscar'], "
                    "input[placeholder*='buscar'], input[placeholder*='search'], "
                    "input[type='search'], input[type='text']"
                )
                if not search_input:
                    raise SourceError("cr.procomer", "Could not find search input field")

                search_input.fill(search_term)
                logger.info("Querying PROCOMER for: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    "button[type='submit'], input[type='submit'], "
                    "button:has-text('Buscar'), button:has-text('Search')"
                )
                if submit:
                    submit.click()
                else:
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
                raise SourceError("cr.procomer", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> CrProcomerResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        rows = page.query_selector_all("table tr, .result-item, .resultado")
        total_results = max(0, len(rows) - 1)

        return CrProcomerResult(
            queried_at=datetime.now(),
            search_term=search_term,
            total_results=total_results,
            details={"raw": body_text.strip()[:500]},
        )
