"""CRC telecom regulator source — Colombia.

Queries CRC for licensed telecom operators by operator name.

URL: https://www.crcom.gov.co/
Input: operator name (custom)
Returns: licensed operators
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.crc import CrcResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CRC_URL = "https://www.crcom.gov.co/es/pagina/operadores-habilitados"


@register
class CrcSource(BaseSource):
    """Query CRC licensed telecom operators by operator name."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.crc",
            display_name="CRC — Operadores de Telecomunicaciones Habilitados",
            description="Colombia CRC telecom regulator: licensed operator lookup by name",
            country="CO",
            url=CRC_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("operator_name", input.document_number).strip()
        if not search_term:
            raise SourceError(
                "co.crc",
                "Provide an operator name (extra.operator_name or document_number)",
            )
        return self._fetch(search_term, audit=input.audit)

    def _fetch(self, search_term: str, audit: bool = False) -> CrcResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying CRC: search_term=%s", search_term)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(CRC_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)
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

                if "habilitado" in body_lower or "licenciado" in body_lower:
                    license_status = "Habilitado"
                elif "no encontr" in body_lower:
                    license_status = "No encontrado"
                else:
                    license_status = "Consultado"

            return CrcResult(
                queried_at=datetime.now(),
                search_term=search_term,
                operator_name=operator_name,
                license_status=license_status,
                details=f"CRC query for: {search_term}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("co.crc", f"Query failed: {e}") from e
