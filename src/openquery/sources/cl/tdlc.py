"""TDLC antitrust tribunal source — Chile.

Queries TDLC for antitrust cases by case number or party name.

URL: https://www.tdlc.cl/
Input: case number or party name (custom)
Returns: case status, details
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.cl.tdlc import TdlcResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

TDLC_URL = "https://www.tdlc.cl/jurisprudencia/"


@register
class TdlcSource(BaseSource):
    """Query TDLC antitrust cases."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="cl.tdlc",
            display_name="TDLC — Tribunal de Defensa de la Libre Competencia",
            description="Chile TDLC antitrust tribunal: case lookup by case number or party",
            country="CL",
            url=TDLC_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("case_number", input.document_number).strip()
        if not search_term:
            raise SourceError(
                "cl.tdlc",
                "Provide a case number or party name (extra.case_number or document_number)",
            )
        return self._fetch(search_term, audit=input.audit)

    def _fetch(self, search_term: str, audit: bool = False) -> TdlcResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying TDLC: search=%s", search_term)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(TDLC_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)
                page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                search_input = page.query_selector(
                    "input[type='search'], input[type='text'], input[name*='s']"
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

                case_number = ""
                status = ""

                for line in body_text.split("\n"):
                    stripped = line.strip()
                    if search_term.lower() in stripped.lower() and not case_number:
                        case_number = stripped

                if "resuelto" in body_lower or "sentencia" in body_lower:
                    status = "Resuelto"
                elif "en tramitación" in body_lower or "pendiente" in body_lower:
                    status = "En tramitación"
                elif "no encontr" in body_lower:
                    status = "No encontrado"
                else:
                    status = "Consultado"

            return TdlcResult(
                queried_at=datetime.now(),
                search_term=search_term,
                case_number=case_number,
                status=status,
                details=f"TDLC query for: {search_term}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("cl.tdlc", f"Query failed: {e}") from e
