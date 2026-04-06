"""Puerto Rico ASUME child support source.

Queries Puerto Rico ASUME (Administración para el Sustento de Menores).
Browser-based, no CAPTCHA.

URL: https://www.asume.pr.gov/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pr.asume import PrAsumeResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

ASUME_URL = "https://www.asume.pr.gov/"


@register
class PrAsumeSource(BaseSource):
    """Query Puerto Rico ASUME child support case status."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pr.asume",
            display_name="ASUME — Sustento de Menores (PR)",
            description="Puerto Rico ASUME: child support case status by case number",
            country="PR",
            url=ASUME_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        case_number = input.extra.get("case_number", "") or input.document_number
        if not case_number:
            raise SourceError("pr.asume", "Case number is required")
        return self._query(case_number.strip(), audit=input.audit)

    def _query(self, case_number: str, audit: bool = False) -> PrAsumeResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("pr.asume", "case_number", case_number)

        with browser.page(ASUME_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    "input[name*='caso'], input[id*='caso'], "
                    "input[name*='case'], input[name*='numero'], input[type='text']"
                )
                if not search_input:
                    raise SourceError("pr.asume", "Could not find case number input field")

                search_input.fill(case_number)
                logger.info("Filled case number: %s", case_number)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    "button[type='submit'], input[type='submit'], button[id*='buscar']"
                )
                if submit:
                    submit.click()
                else:
                    search_input.press("Enter")

                page.wait_for_timeout(3000)
                page.wait_for_selector(
                    "table, .resultado, .result, #resultado",
                    timeout=15000,
                )

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, case_number)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("pr.asume", f"Query failed: {e}") from e

    def _parse_result(self, page, case_number: str) -> PrAsumeResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = PrAsumeResult(queried_at=datetime.now(), case_number=case_number)

        field_patterns = {
            "estado": "status",
            "status": "status",
            "estatus": "status",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_patterns.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value and not getattr(result, field):
                        setattr(result, field, value)
                    break

        rows = page.query_selector_all("table tr")
        if len(rows) >= 2:
            cells = rows[1].query_selector_all("td")
            if cells:
                values = [(c.inner_text() or "").strip() for c in cells]
                if len(values) >= 1 and not result.status:
                    result.status = values[0]

        return result
