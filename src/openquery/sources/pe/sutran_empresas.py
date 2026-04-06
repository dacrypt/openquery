"""SUTRAN transport companies source — Peru.

Queries SUTRAN for transport company licenses by name.

URL: https://www.sutran.gob.pe/
Input: company name (custom)
Returns: transport license status
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pe.sutran_empresas import SutranEmpresasResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SUTRAN_URL = "https://www.sutran.gob.pe/empresas-habilitadas/"


@register
class SutranEmpresasSource(BaseSource):
    """Query SUTRAN transport company licenses by name."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pe.sutran_empresas",
            display_name="SUTRAN — Empresas de Transporte Habilitadas",
            description="Peru SUTRAN transport company license lookup by name",
            country="PE",
            url=SUTRAN_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("company_name", input.document_number).strip()
        if not search_term:
            raise SourceError(
                "pe.sutran_empresas",
                "Provide a company name (extra.company_name or document_number)",
            )
        return self._fetch(search_term, audit=input.audit)

    def _fetch(self, search_term: str, audit: bool = False) -> SutranEmpresasResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying SUTRAN empresas: search_term=%s", search_term)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(SUTRAN_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)
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

                if "habilitada" in body_lower or "autorizada" in body_lower:
                    license_status = "Habilitada"
                elif "no encontr" in body_lower:
                    license_status = "No encontrada"
                else:
                    license_status = "Consultada"

            return SutranEmpresasResult(
                queried_at=datetime.now(),
                search_term=search_term,
                company_name=company_name,
                license_status=license_status,
                details=f"SUTRAN empresas query for: {search_term}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("pe.sutran_empresas", f"Query failed: {e}") from e
