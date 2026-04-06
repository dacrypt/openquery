"""SUBTEL telecom operator source — Chile.

Queries SUBTEL for licensed telecom operators.

URL: https://www.subtel.gob.cl/
Input: operator name (custom)
Returns: license status
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.cl.subtel import SubtelResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SUBTEL_URL = "https://www.subtel.gob.cl/informacion-estadistica-e-institucional/registros/"


@register
class SubtelSource(BaseSource):
    """Query SUBTEL licensed telecom operators."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="cl.subtel",
            display_name="SUBTEL — Operadores de Telecomunicaciones",
            description="Chile SUBTEL: licensed telecom operator lookup",
            country="CL",
            url=SUBTEL_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("operator_name", input.document_number).strip()
        if not search_term:
            raise SourceError(
                "cl.subtel",
                "Provide an operator name (extra.operator_name or document_number)",
            )
        return self._fetch(search_term, audit=input.audit)

    def _fetch(self, search_term: str, audit: bool = False) -> SubtelResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying SUBTEL: operator=%s", search_term)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(SUBTEL_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)
                page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                search_input = page.query_selector(
                    "input[type='search'], input[type='text'], input[placeholder*='operador' i]"
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

                operator_name = ""
                license_status = ""

                for line in body_text.split("\n"):
                    if search_term.lower() in line.lower() and not operator_name:
                        operator_name = line.strip()

                if "autorizado" in body_lower or "concesionario" in body_lower:
                    license_status = "Autorizado"
                elif "no encontr" in body_lower:
                    license_status = "No encontrado"
                else:
                    license_status = "Consultado"

            return SubtelResult(
                queried_at=datetime.now(),
                search_term=search_term,
                operator_name=operator_name or search_term,
                license_status=license_status,
                details=f"SUBTEL query for: {search_term}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("cl.subtel", f"Query failed: {e}") from e
