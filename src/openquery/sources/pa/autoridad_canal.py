"""ACP Panama Canal Authority source — Panama.

Queries ACP for canal tenders and statistics.

URL: https://pancanal.com/
Input: search term (custom)
Returns: total results, details
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pa.autoridad_canal import AutoridadCanalResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

ACP_URL = "https://pancanal.com/en/business-opportunities/"


@register
class AutoridadCanalSource(BaseSource):
    """Query ACP Panama Canal Authority for tenders and statistics."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pa.autoridad_canal",
            display_name="ACP — Autoridad del Canal de Panamá",
            description="Panama ACP Canal Authority: business opportunities and tenders lookup",
            country="PA",
            url=ACP_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("search_term", input.document_number).strip()
        if not search_term:
            raise SourceError(
                "pa.autoridad_canal",
                "Provide a search term (extra.search_term or document_number)",
            )
        return self._fetch(search_term, audit=input.audit)

    def _fetch(self, search_term: str, audit: bool = False) -> AutoridadCanalResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying ACP: search=%s", search_term)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(ACP_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)
                page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                search_input = page.query_selector(
                    "input[type='search'], input[type='text'], input[name*='s']"
                )
                if search_input:
                    search_input.fill(search_term)
                    submit = page.query_selector("button[type='submit'], input[type='submit']")
                    if submit:
                        submit.click()
                    else:
                        search_input.press("Enter")
                    page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                body_text = page.inner_text("body")
                body_lower = body_text.lower()

                total_results = body_lower.count(search_term.lower())
                details = f"ACP query for: {search_term}"

            return AutoridadCanalResult(
                queried_at=datetime.now(),
                search_term=search_term,
                total_results=total_results,
                details=details,
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("pa.autoridad_canal", f"Query failed: {e}") from e
