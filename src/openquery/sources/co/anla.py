"""ANLA environmental licenses source — Colombia.

Queries ANLA for environmental permits by company name.

URL: https://www.anla.gov.co/
Input: company name (custom)
Returns: environmental permits and license status
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.anla import AnlaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

ANLA_URL = "https://www.anla.gov.co/01_anla/expedientes"


@register
class AnlaSource(BaseSource):
    """Query ANLA environmental permits by company name."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.anla",
            display_name="ANLA — Licencias Ambientales",
            description="Colombia ANLA environmental permits and licenses lookup by company name",
            country="CO",
            url=ANLA_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("company_name", input.document_number).strip()
        if not search_term:
            raise SourceError(
                "co.anla",
                "Provide a company name (extra.company_name or document_number)",
            )
        return self._fetch(search_term, audit=input.audit)

    def _fetch(self, search_term: str, audit: bool = False) -> AnlaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying ANLA: search_term=%s", search_term)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(ANLA_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)
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
                body_lower = body_text.lower()

                company_name = ""
                license_status = ""

                for line in body_text.split("\n"):
                    if search_term.lower() in line.lower() and not company_name:
                        company_name = line.strip()

                if "vigente" in body_lower:
                    license_status = "Vigente"
                elif "suspendida" in body_lower:
                    license_status = "Suspendida"
                elif "encontr" in body_lower:
                    license_status = "Encontrada"
                else:
                    license_status = "No encontrada"

            return AnlaResult(
                queried_at=datetime.now(),
                search_term=search_term,
                company_name=company_name,
                license_status=license_status,
                details=f"ANLA query for: {search_term}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("co.anla", f"Query failed: {e}") from e
