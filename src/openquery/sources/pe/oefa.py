"""OEFA environmental enforcement source — Peru.

Queries OEFA for environmental sanctions by company name.

URL: https://www.oefa.gob.pe/
Input: company name (custom)
Returns: environmental sanctions
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pe.oefa import OefaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

OEFA_URL = "https://www.oefa.gob.pe/resoluciones"


@register
class OefaSource(BaseSource):
    """Query OEFA environmental sanctions by company name."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pe.oefa",
            display_name="OEFA — Sanciones Ambientales",
            description="Peru OEFA environmental enforcement and sanctions lookup by company name",
            country="PE",
            url=OEFA_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("company_name", input.document_number).strip()
        if not search_term:
            raise SourceError(
                "pe.oefa",
                "Provide a company name (extra.company_name or document_number)",
            )
        return self._fetch(search_term, audit=input.audit)

    def _fetch(self, search_term: str, audit: bool = False) -> OefaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying OEFA: search_term=%s", search_term)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(OEFA_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)
                page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                search_input = page.query_selector(
                    "input[type='search'], input[type='text'], input[placeholder*='empresa' i]"
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

                company_name = ""
                total_sanctions = 0

                for line in body_text.split("\n"):
                    if search_term.lower() in line.lower() and not company_name:
                        company_name = line.strip()

                rows = page.query_selector_all("table tbody tr, .result-row, .row")
                total_sanctions = len(rows)

            return OefaResult(
                queried_at=datetime.now(),
                search_term=search_term,
                company_name=company_name,
                total_sanctions=total_sanctions,
                details=f"OEFA query for: {search_term}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("pe.oefa", f"Query failed: {e}") from e
