"""Poder Judicial source — Dominican Republic court cases lookup.

Queries Dominican Republic's Poder Judicial portal for court case status
by case number or party name.

Source: https://www.poderjudicial.gob.do/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.do.poder_judicial import DoPodeJudicialResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

PODER_JUDICIAL_URL = "https://www.poderjudicial.gob.do/"


@register
class DoPodeJudicialSource(BaseSource):
    """Query Dominican Republic Poder Judicial court cases."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="do.poder_judicial",
            display_name="Poder Judicial — Consulta de Casos",
            description=(
                "Dominican Republic Poder Judicial: court case status by case number or party name"
            ),
            country="DO",
            url=PODER_JUDICIAL_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (
            input.extra.get("case_number", "")
            or input.extra.get("party_name", "")
            or input.document_number.strip()
        )
        if not search_term:
            raise SourceError("do.poder_judicial", "Case number or party name is required")
        return self._query(search_term=search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> DoPodeJudicialResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("do.poder_judicial", "search_term", search_term)

        with browser.page(PODER_JUDICIAL_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "page_loaded")

                search_input = page.query_selector(
                    'input[name*="caso"], input[name*="expediente"], '
                    'input[name*="search"], input[id*="caso"], '
                    'input[id*="expediente"], input[placeholder*="caso"], '
                    'input[placeholder*="expediente"], input[type="search"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("do.poder_judicial", "Could not find search input field")

                search_input.fill(search_term)
                logger.info("Querying Poder Judicial for: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit_btn = page.query_selector(
                    'input[type="submit"], button[type="submit"], '
                    'button:has-text("Consultar"), button:has-text("Buscar"), '
                    'input[value*="Consultar"], input[value*="Buscar"]'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    search_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_term)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("do.poder_judicial", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> DoPodeJudicialResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        case_number = ""
        court = ""
        status = ""

        field_map = {
            "expediente": "case_number",
            "número de caso": "case_number",
            "caso": "case_number",
            "tribunal": "court",
            "juzgado": "court",
            "corte": "court",
            "estado": "status",
            "estatus": "status",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_map.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value:
                        if field == "case_number" and not case_number:
                            case_number = value
                        elif field == "court" and not court:
                            court = value
                        elif field == "status" and not status:
                            status = value
                    break

        return DoPodeJudicialResult(
            queried_at=datetime.now(),
            search_term=search_term,
            case_number=case_number,
            court=court,
            status=status,
            details=body_text.strip()[:500],
        )
