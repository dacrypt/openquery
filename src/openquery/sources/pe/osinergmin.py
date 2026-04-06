"""OSINERGMIN energy/mining supervisor source — Peru.

Queries OSINERGMIN for supervised energy/mining entities.

URL: https://www.osinergmin.gob.pe/
Input: company name (custom)
Returns: company status
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pe.osinergmin import OsinergminResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

OSINERGMIN_URL = "https://www.osinergmin.gob.pe/empresas/supervisadas"


@register
class OsinergminSource(BaseSource):
    """Query OSINERGMIN supervised energy/mining entity status."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pe.osinergmin",
            display_name="OSINERGMIN — Empresas Supervisadas",
            description="Peru OSINERGMIN energy/mining supervisor: supervised entity lookup",
            country="PE",
            url=OSINERGMIN_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("company_name", input.document_number).strip()
        if not search_term:
            raise SourceError(
                "pe.osinergmin",
                "Provide a company name (extra.company_name or document_number)",
            )
        return self._fetch(search_term, audit=input.audit)

    def _fetch(self, search_term: str, audit: bool = False) -> OsinergminResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying OSINERGMIN: company=%s", search_term)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(OSINERGMIN_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)  # noqa: E501
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
                status = ""

                for line in body_text.split("\n"):
                    if search_term.lower() in line.lower() and not company_name:
                        company_name = line.strip()

                if "supervisada" in body_lower or "activa" in body_lower:
                    status = "Supervisada"
                elif "no encontr" in body_lower or "sin resultado" in body_lower:
                    status = "No encontrada"
                else:
                    status = "Consultada"

            return OsinergminResult(
                queried_at=datetime.now(),
                search_term=search_term,
                company_name=company_name or search_term,
                status=status,
                details=f"OSINERGMIN query for: {search_term}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("pe.osinergmin", f"Query failed: {e}") from e
