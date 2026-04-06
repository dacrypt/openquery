"""Honduras Poder Judicial source — SEJE court cases.

Queries Honduras' Sistema de Expedientes Judiciales Electrónicos (SEJE)
for court case data by case number.

Flow:
1. Navigate to https://sejedata.poderjudicial.gob.hn/sejeinfo/
2. Enter case number
3. Submit and parse court, status, proceedings

Source: https://sejedata.poderjudicial.gob.hn/sejeinfo/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.hn.poder_judicial import HnPoderJudicialResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

PODER_JUDICIAL_URL = "https://sejedata.poderjudicial.gob.hn/sejeinfo/"


@register
class HnPoderJudicialSource(BaseSource):
    """Query Honduras Poder Judicial SEJE court cases by case number."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="hn.poder_judicial",
            display_name="Poder Judicial — SEJE Honduras",
            description="Honduras court cases: status, proceedings, court (Sistema de Expedientes Judiciales)",  # noqa: E501
            country="HN",
            url=PODER_JUDICIAL_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        case_number = input.extra.get("case_number", "") or input.document_number
        if not case_number:
            raise SourceError("hn.poder_judicial", "case_number or document_number is required")
        return self._query(case_number.strip(), audit=input.audit)

    def _query(self, case_number: str, audit: bool = False) -> HnPoderJudicialResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("hn.poder_judicial", "case_number", case_number)

        with browser.page(PODER_JUDICIAL_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill case number input
                case_input = page.query_selector(
                    'input[id*="expediente"], input[name*="expediente"], '
                    'input[id*="caso"], input[name*="caso"], '
                    'input[id*="numero"], input[name*="numero"], '
                    'input[type="text"]'
                )
                if not case_input:
                    raise SourceError("hn.poder_judicial", "Could not find case number input field")

                case_input.fill(case_number)
                logger.info("Filled case number: %s", case_number)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="consultar"], button[id*="buscar"], '
                    'button:has-text("Consultar"), button:has-text("Buscar")'
                )
                if submit:
                    submit.click()
                else:
                    case_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, case_number)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("hn.poder_judicial", f"Query failed: {e}") from e

    def _parse_result(self, page, case_number: str) -> HnPoderJudicialResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = HnPoderJudicialResult(queried_at=datetime.now(), case_number=case_number)
        details: dict[str, str] = {}

        field_map = {
            "juzgado": "court",
            "tribunal": "court",
            "sala": "court",
            "estado": "status",
            "actuacion": "proceedings",
            "actuación": "proceedings",
            "diligencia": "proceedings",
            "expediente": "case_number",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            lower = stripped.lower()
            for label, attr in field_map.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value:
                        setattr(result, attr, value)
                    break
            # Collect all key:value pairs into details
            if ":" in stripped:
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip()
                if key and val:
                    details[key] = val

        result.details = details
        return result
