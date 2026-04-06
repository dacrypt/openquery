"""CONRED source — Guatemala disaster/emergency events.

Queries Guatemala CONRED (Coordinadora Nacional para la Reducción de Desastres)
for emergency and disaster events by search term. Browser-based, no CAPTCHA.

URL: https://www.conred.gob.gt/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.gt.conred import GtConredResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CONRED_URL = "https://www.conred.gob.gt/"


@register
class GtConredSource(BaseSource):
    """Query Guatemala CONRED for disaster and emergency events."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="gt.conred",
            display_name="CONRED — Desastres y Emergencias (GT)",
            description="Guatemala CONRED emergency and disaster events by search keyword",
            country="GT",
            url=CONRED_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("search_term", "") or input.document_number
        if not search_term:
            raise SourceError("gt.conred", "Search term is required")
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> GtConredResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("gt.conred", "search_term", search_term)

        with browser.page(CONRED_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "page_loaded")

                search_input = page.query_selector(
                    "input[name*='search'], input[name*='buscar'], input[name*='evento'], "
                    "input[id*='search'], input[id*='buscar'], "
                    "input[placeholder*='buscar'], input[placeholder*='evento'], "
                    "input[type='search'], input[type='text']"
                )
                if not search_input:
                    raise SourceError("gt.conred", "Could not find search input field")

                search_input.fill(search_term)
                logger.info("Querying CONRED for: %s", search_term)

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
                raise SourceError("gt.conred", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> GtConredResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        events = []

        event_elements = page.query_selector_all(
            "article, .evento, .event, .emergencia, table tr"
        )
        for elem in event_elements[:20]:
            title_el = elem.query_selector("h1, h2, h3, h4, .title, .titulo, td")
            date_el = elem.query_selector("time, .date, .fecha")
            title = (title_el.inner_text() or "").strip() if title_el else ""
            date = (date_el.inner_text() or "").strip() if date_el else ""
            if title:
                events.append({"title": title, "date": date})

        return GtConredResult(
            queried_at=datetime.now(),
            search_term=search_term,
            total_events=len(events),
            events=events,
            details={"raw": body_text.strip()[:500]},
        )
