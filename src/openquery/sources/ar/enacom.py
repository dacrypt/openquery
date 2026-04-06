"""ENACOM telecom regulator source — Argentina.

Queries ENACOM for licensed telecom operators.

URL: https://www.enacom.gob.ar/
Input: company name (custom)
Returns: license status
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ar.enacom import EnacomResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

ENACOM_URL = "https://www.enacom.gob.ar/prestadores_p3003"


@register
class EnacomSource(BaseSource):
    """Query ENACOM licensed telecom operators."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ar.enacom",
            display_name="ENACOM — Prestadores de Telecomunicaciones",
            description="Argentina ENACOM: licensed telecom operator lookup",
            country="AR",
            url=ENACOM_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("company_name", input.document_number).strip()
        if not search_term:
            raise SourceError(
                "ar.enacom",
                "Provide a company name (extra.company_name or document_number)",
            )
        return self._fetch(search_term, audit=input.audit)

    def _fetch(self, search_term: str, audit: bool = False) -> EnacomResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying ENACOM: company=%s", search_term)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(ENACOM_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)
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

                if "habilitado" in body_lower or "autorizado" in body_lower:
                    license_status = "Habilitado"
                elif "suspendido" in body_lower or "cancelado" in body_lower:
                    license_status = "Suspendido/Cancelado"
                elif "no encontr" in body_lower:
                    license_status = "No encontrado"
                else:
                    license_status = "Consultado"

            return EnacomResult(
                queried_at=datetime.now(),
                search_term=search_term,
                company_name=company_name or search_term,
                license_status=license_status,
                details=f"ENACOM query for: {search_term}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("ar.enacom", f"Query failed: {e}") from e
