"""CREG energy regulator source — Colombia.

Queries CREG for regulated energy entities by company name.

URL: https://www.creg.gov.co/
Input: company name (custom)
Returns: regulated entities
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.creg import CregResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CREG_URL = "https://www.creg.gov.co/es/servicios-al-usuario/consulta-de-empresas-del-sector"


@register
class CregSource(BaseSource):
    """Query CREG regulated energy entities by company name."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.creg",
            display_name="CREG — Empresas del Sector Energético",
            description="Colombia CREG energy regulator: regulated entity lookup by company name",
            country="CO",
            url=CREG_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("company_name", input.document_number).strip()
        if not search_term:
            raise SourceError(
                "co.creg",
                "Provide a company name (extra.company_name or document_number)",
            )
        return self._fetch(search_term, audit=input.audit)

    def _fetch(self, search_term: str, audit: bool = False) -> CregResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying CREG: search_term=%s", search_term)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(CREG_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)
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

                entity_name = ""
                regulation_status = ""

                for line in body_text.split("\n"):
                    if search_term.lower() in line.lower() and not entity_name:
                        entity_name = line.strip()

                if "regulada" in body_lower or "registrada" in body_lower:
                    regulation_status = "Regulada"
                elif "no encontr" in body_lower:
                    regulation_status = "No encontrada"
                else:
                    regulation_status = "Consultada"

            return CregResult(
                queried_at=datetime.now(),
                search_term=search_term,
                entity_name=entity_name,
                regulation_status=regulation_status,
                details=f"CREG query for: {search_term}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("co.creg", f"Query failed: {e}") from e
