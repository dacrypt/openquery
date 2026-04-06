"""PRODUCE fisheries/industry registration source — Peru.

Queries PRODUCE for fisheries and industrial company registrations.

URL: https://www.produce.gob.pe/
Input: company name (custom)
Returns: registration status
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pe.produce import ProduceResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

PRODUCE_URL = "https://www.produce.gob.pe/index.php/tramites-y-servicios/consultas"


@register
class ProduceSource(BaseSource):
    """Query PRODUCE fisheries/industry registration status."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pe.produce",
            display_name="PRODUCE — Registro Industrial y Pesquero",
            description="Peru PRODUCE ministry: fisheries and industrial registration lookup",
            country="PE",
            url=PRODUCE_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("company_name", input.document_number).strip()
        if not search_term:
            raise SourceError(
                "pe.produce",
                "Provide a company name (extra.company_name or document_number)",
            )
        return self._fetch(search_term, audit=input.audit)

    def _fetch(self, search_term: str, audit: bool = False) -> ProduceResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying PRODUCE: company=%s", search_term)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(PRODUCE_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)
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
                registration_status = ""

                for line in body_text.split("\n"):
                    if search_term.lower() in line.lower() and not company_name:
                        company_name = line.strip()

                if "registrada" in body_lower or "habilitada" in body_lower:
                    registration_status = "Registrada"
                elif "no encontr" in body_lower or "sin resultado" in body_lower:
                    registration_status = "No encontrada"
                else:
                    registration_status = "Consultada"

            return ProduceResult(
                queried_at=datetime.now(),
                search_term=search_term,
                company_name=company_name or search_term,
                registration_status=registration_status,
                details=f"PRODUCE query for: {search_term}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("pe.produce", f"Query failed: {e}") from e
