"""INACIF source — Guatemala forensic registry.

Queries the Instituto Nacional de Ciencias Forenses (INACIF) for forensic
case records.

Source: https://www.inacif.gob.gt/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.gt.inacif import InacifResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

INACIF_URL = "https://www.inacif.gob.gt/"


@register
class InacifSource(BaseSource):
    """Query Guatemala INACIF forensic registry by case number."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="gt.inacif",
            display_name="INACIF — Registro Forense",
            description=(
                "Guatemala INACIF: forensic case registry by case number"
            ),
            country="GT",
            url=INACIF_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        case_number = input.extra.get("case_number", "") or input.document_number.strip()
        if not case_number:
            raise SourceError("gt.inacif", "Case number is required")
        return self._query(case_number=case_number, audit=input.audit)

    def _query(self, case_number: str, audit: bool = False) -> InacifResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("gt.inacif", "case_number", case_number)

        with browser.page(INACIF_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "page_loaded")

                search_input = page.query_selector(
                    'input[name*="caso"], input[id*="caso"], '
                    'input[name*="expediente"], input[type="text"], '
                    'input[name*="numero"], input[type="search"]'
                )
                if search_input:
                    search_input.fill(case_number)
                    logger.info("Querying INACIF for case: %s", case_number)

                    submit_btn = page.query_selector(
                        'button[type="submit"], input[type="submit"], '
                        'button:has-text("Consultar"), button:has-text("Buscar")'
                    )
                    if submit_btn:
                        submit_btn.click()
                    else:
                        search_input.press("Enter")

                    page.wait_for_timeout(4000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, case_number)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("gt.inacif", f"Query failed: {e}") from e

    def _parse_result(self, page, case_number: str) -> InacifResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        case_type = ""
        status = ""
        date_registered = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if any(kw in lower for kw in ["tipo", "type", "clase"]) and ":" in stripped and not case_type:  # noqa: E501
                case_type = stripped.split(":", 1)[1].strip()
            elif "estado" in lower and ":" in stripped and not status:
                status = stripped.split(":", 1)[1].strip()
            elif any(kw in lower for kw in ["fecha", "date"]) and ":" in stripped and not date_registered:  # noqa: E501
                date_registered = stripped.split(":", 1)[1].strip()

        return InacifResult(
            queried_at=datetime.now(),
            case_number=case_number,
            case_type=case_type,
            status=status,
            date_registered=date_registered,
            details=body_text.strip()[:500],
        )
