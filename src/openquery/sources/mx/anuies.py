"""ANUIES university data source — Mexico.

Queries ANUIES for university and institution data.

URL: https://www.anuies.mx/
Input: institution name (custom)
Returns: university data
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.mx.anuies import AnuiesResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

ANUIES_URL = "https://www.anuies.mx/servicios/p_anuies/index2.php"


@register
class AnuiesSource(BaseSource):
    """Query ANUIES Mexico university registry data."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="mx.anuies",
            display_name="ANUIES — Directorio de Instituciones de Educación Superior",
            description="Mexico ANUIES university directory and institution data",
            country="MX",
            url=ANUIES_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("institution_name", input.document_number).strip()
        if not search_term:
            raise SourceError(
                "mx.anuies",
                "Provide an institution name (extra.institution_name or document_number)",
            )
        return self._fetch(search_term, audit=input.audit)

    def _fetch(self, search_term: str, audit: bool = False) -> AnuiesResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying ANUIES: search_term=%s", search_term)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(ANUIES_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)
                page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                search_input = page.query_selector(
                    "input[name*='nombre'], input[type='text'], input[placeholder*='institución' i]"
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
                institution_name = ""

                for line in body_text.split("\n"):
                    if search_term.lower() in line.lower():
                        institution_name = line.strip()
                        break

            return AnuiesResult(
                queried_at=datetime.now(),
                search_term=search_term,
                institution_name=institution_name,
                details=f"ANUIES query for: {search_term}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("mx.anuies", f"Query failed: {e}") from e
