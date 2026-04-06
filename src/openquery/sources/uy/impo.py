"""Uruguay IMPO legal norms database source.

Queries IMPO (Imprenta Nacional) for legislation and legal norms
by search term.

URL: https://www.impo.com.uy/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.uy.impo import UyImpoNorm, UyImpoResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

IMPO_URL = "https://www.impo.com.uy/"
IMPO_SEARCH_URL = "https://www.impo.com.uy/bases/busqueda-simple"


@register
class UyImpoSource(BaseSource):
    """Query Uruguay IMPO legal norms database."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="uy.impo",
            display_name="IMPO — Base de Normas Jurídicas Uruguay",
            description=(
                "Uruguay IMPO legal norms database: legislation, laws, and decrees "
                "by search term"
            ),
            country="UY",
            url=IMPO_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query IMPO for legal norms."""
        search_term = input.extra.get("search_term", "") or input.document_number
        if not search_term:
            raise SourceError("uy.impo", "search_term is required")
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> UyImpoResult:
        """Full flow: launch browser, fill form, parse results."""
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("uy.impo", "search_term", search_term)

        with browser.page(IMPO_SEARCH_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[id*="texto"], input[name*="texto"], '
                    'input[id*="busqueda"], input[name*="busqueda"], '
                    'input[id*="search"], input[name*="search"], '
                    'input[type="text"], input[type="search"]'
                )
                if not search_input:
                    raise SourceError("uy.impo", "Could not find search input field")

                search_input.fill(search_term)
                logger.info("Filled search term: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button:has-text("Buscar"), input[value="Buscar"]'
                )
                if submit:
                    submit.click()
                else:
                    search_input.press("Enter")

                page.wait_for_timeout(4000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_term)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("uy.impo", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> UyImpoResult:
        """Parse legal norms data from the page DOM."""
        body_text = page.inner_text("body")
        result = UyImpoResult(search_term=search_term)
        details: dict[str, str] = {}
        norms: list[UyImpoNorm] = []

        rows = page.query_selector_all(".resultado, .norm-item, table tr, li.result")
        for row in rows:
            text = (row.inner_text() or "").strip()
            if not text:
                continue
            link = row.query_selector("a")
            url = ""
            title = text[:200]
            if link:
                url = link.get_attribute("href") or ""
                title = (link.inner_text() or text).strip()[:200]
                if url and not url.startswith("http"):
                    url = f"https://www.impo.com.uy{url}"
            norms.append(UyImpoNorm(title=title, url=url))

        result.norms = norms
        result.total_results = len(norms)

        for line in body_text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            if ":" in stripped:
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip()
                if key and val and len(key) < 60:
                    details[key] = val

        result.details = details
        logger.info(
            "IMPO result — search=%s, norms=%d", search_term, result.total_results
        )
        return result
