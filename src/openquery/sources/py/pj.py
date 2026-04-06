"""Paraguay Poder Judicial source — court case lookup.

Queries the Paraguayan Supreme Court (CSJ) for case status,
actions, and parties by case number.

Source: https://www.csj.gov.py/consultacasojudicial
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.py.pj import PyPjResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CSJ_URL = "https://www.csj.gov.py/consultacasojudicial"


@register
class PyPjSource(BaseSource):
    """Query Paraguayan Poder Judicial court cases by case number."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="py.pj",
            display_name="CSJ — Consulta de Caso Judicial",
            description="Paraguay court case status, actions, and parties (Corte Suprema de Justicia)",  # noqa: E501
            country="PY",
            url=CSJ_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        case_number = input.document_number or input.extra.get("case_number", "")
        if not case_number:
            raise SourceError("py.pj", "Case number is required")
        return self._query(case_number.strip(), audit=input.audit)

    def _query(self, case_number: str, audit: bool = False) -> PyPjResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("py.pj", "custom", case_number)

        with browser.page(CSJ_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                case_input = page.query_selector(
                    'input[name*="caso"], input[id*="caso"], '
                    'input[name*="expediente"], input[id*="expediente"], '
                    'input[name*="numero"], input[type="text"]'
                )
                if not case_input:
                    raise SourceError("py.pj", "Could not find case number input field")

                case_input.fill(case_number)
                logger.info("Filled case number: %s", case_number)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button:has-text("Buscar"), button:has-text("Consultar")'
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
                raise SourceError("py.pj", f"Query failed: {e}") from e

    def _parse_result(self, page, case_number: str) -> PyPjResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = PyPjResult(queried_at=datetime.now(), case_number=case_number)

        field_map = {
            "estado": "status",
            "situacion": "status",
            "juzgado": "court",
            "tribunal": "court",
            "sala": "court",
            "partes": "parties",
            "demandante": "parties",
            "ultima actuacion": "last_action",
            "ultimo movimiento": "last_action",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_map.items():
                if label in lower and (":" in stripped or "\t" in stripped):
                    sep = ":" if ":" in stripped else "\t"
                    value = stripped.split(sep, 1)[1].strip()
                    if value and not getattr(result, field):
                        setattr(result, field, value)
                    break

        if body_text.strip():
            result.details = body_text.strip()[:500]

        return result
