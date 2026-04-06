"""ABI source — Bolivia government news agency articles.

Queries ABI (Agencia Boliviana de Información) for news articles
by search term. Browser-based, no CAPTCHA.

URL: https://www.abi.bo/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.bo.abi import BoAbiResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

ABI_URL = "https://www.abi.bo/"


@register
class BoAbiSource(BaseSource):
    """Query Bolivia ABI news agency for articles by search term."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="bo.abi",
            display_name="ABI — Agencia Boliviana de Información",
            description="Bolivia ABI government news agency: search articles by keyword",
            country="BO",
            url=ABI_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("search_term", "") or input.document_number
        if not search_term:
            raise SourceError("bo.abi", "Search term is required")
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> BoAbiResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("bo.abi", "search_term", search_term)

        with browser.page(ABI_URL) as page:
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
                    raise SourceError("bo.abi", "Could not find search input field")

                search_input.fill(search_term)
                logger.info("Querying ABI for: %s", search_term)

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
                raise SourceError("bo.abi", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> BoAbiResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        articles = []

        article_elements = page.query_selector_all("article, .article, .noticia, .news-item")
        for elem in article_elements[:20]:
            title_el = elem.query_selector("h1, h2, h3, h4, .title, .titulo")
            date_el = elem.query_selector("time, .date, .fecha")
            title = (title_el.inner_text() or "").strip() if title_el else ""
            date = (date_el.inner_text() or "").strip() if date_el else ""
            if title:
                articles.append({"title": title, "date": date})

        return BoAbiResult(
            queried_at=datetime.now(),
            search_term=search_term,
            total_results=len(articles),
            articles=articles,
            details={"raw": body_text.strip()[:500]},
        )
