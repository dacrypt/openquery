"""CONATEL telecom regulator source — Venezuela.

Queries CONATEL for licensed telecom operators.

URL: https://www.conatel.gob.ve/
Input: operator name (custom)
Returns: license status
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ve.conatel import ConatelResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CONATEL_URL = "https://www.conatel.gob.ve/operadoras-habilitadas/"


@register
class ConatelSource(BaseSource):
    """Query CONATEL licensed telecom operators."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ve.conatel",
            display_name="CONATEL — Operadoras Habilitadas",
            description="Venezuela CONATEL: licensed telecom operator lookup",
            country="VE",
            url=CONATEL_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("operator_name", input.document_number).strip()
        if not search_term:
            raise SourceError(
                "ve.conatel",
                "Provide an operator name (extra.operator_name or document_number)",
            )
        return self._fetch(search_term, audit=input.audit)

    def _fetch(self, search_term: str, audit: bool = False) -> ConatelResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying CONATEL Venezuela: operator=%s", search_term)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(CONATEL_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)
                page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                body_text = page.inner_text("body")
                body_text.lower()

                operator_name = ""
                license_status = ""

                for line in body_text.split("\n"):
                    if search_term.lower() in line.lower() and not operator_name:
                        operator_name = line.strip()
                        license_status = "Habilitada"
                        break

                if not license_status:
                    license_status = "No encontrada"

            return ConatelResult(
                queried_at=datetime.now(),
                search_term=search_term,
                operator_name=operator_name or search_term,
                license_status=license_status,
                details=f"CONATEL Venezuela query for: {search_term}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("ve.conatel", f"Query failed: {e}") from e
