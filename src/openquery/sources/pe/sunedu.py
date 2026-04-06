"""SUNEDU university accreditation source — Peru.

Queries SUNEDU for university accreditation status.

URL: https://www.sunedu.gob.pe/
Input: university name (custom)
Returns: accreditation status
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pe.sunedu import SuneduResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SUNEDU_URL = "https://www.sunedu.gob.pe/lista-de-universidades-licenciadas/"


@register
class SuneduSource(BaseSource):
    """Query SUNEDU university accreditation status."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pe.sunedu",
            display_name="SUNEDU — Licenciamiento Universitario",
            description="Peru SUNEDU university accreditation and licensing status",
            country="PE",
            url=SUNEDU_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("university_name", input.document_number).strip()
        if not search_term:
            raise SourceError(
                "pe.sunedu",
                "Provide a university name (extra.university_name or document_number)",
            )
        return self._fetch(search_term, audit=input.audit)

    def _fetch(self, search_term: str, audit: bool = False) -> SuneduResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying SUNEDU: search_term=%s", search_term)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(SUNEDU_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)
                page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                search_input = page.query_selector(
                    "input[type='search'], input[type='text'], input[placeholder*='buscar' i]"
                )
                if search_input:
                    search_input.fill(search_term)
                    page.keyboard.press("Enter")
                    page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                body_text = page.inner_text("body")
                body_lower = body_text.lower()
                search_lower = search_term.lower()

                university_name = ""
                accreditation_status = ""

                found = search_lower in body_lower
                if found:
                    for line in body_text.split("\n"):
                        if search_term.lower() in line.lower():
                            university_name = line.strip()
                            break
                    accreditation_status = "Licenciada" if "licenciad" in body_lower else "No encontrada"  # noqa: E501
                else:
                    accreditation_status = "No encontrada"

            return SuneduResult(
                queried_at=datetime.now(),
                search_term=search_term,
                university_name=university_name,
                accreditation_status=accreditation_status,
                details=f"SUNEDU query for: {search_term}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("pe.sunedu", f"Query failed: {e}") from e
