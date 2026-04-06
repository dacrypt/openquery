"""Uruguay Poder Judicial source — case lookup.

Queries the Uruguayan Poder Judicial for case status, last action,
and history by SUI case number.

Source: https://expedientes.poderjudicial.gub.uy/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.uy.pj import UyPjResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

PJ_URL = "https://expedientes.poderjudicial.gub.uy/"


@register
class UyPjSource(BaseSource):
    """Query Uruguayan Poder Judicial case registry by SUI number."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="uy.pj",
            display_name="Poder Judicial — Expedientes",
            description="Uruguay judicial case: status, last action, history (Poder Judicial)",
            country="UY",
            url=PJ_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        sui = input.document_number or input.extra.get("sui", "")
        if not sui:
            raise SourceError("uy.pj", "SUI case number is required")
        return self._query(sui.strip(), audit=input.audit)

    def _query(self, sui: str, audit: bool = False) -> UyPjResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("uy.pj", "custom", sui)

        with browser.page(PJ_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                sui_input = page.query_selector(
                    'input[name*="sui"], input[id*="sui"], '
                    'input[name*="expediente"], input[id*="expediente"], '
                    'input[name*="ficha"], input[type="text"]'
                )
                if not sui_input:
                    raise SourceError("uy.pj", "Could not find SUI input field")

                sui_input.fill(sui)
                logger.info("Filled SUI: %s", sui)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button:has-text("Buscar"), button:has-text("Consultar")'
                )
                if submit:
                    submit.click()
                else:
                    sui_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, sui)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("uy.pj", f"Query failed: {e}") from e

    def _parse_result(self, page, sui: str) -> UyPjResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = UyPjResult(queried_at=datetime.now(), sui=sui)

        field_map = {
            "estado": "case_status",
            "situacion": "case_status",
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
                    if value:
                        setattr(result, field, value)
                    break

        if body_text.strip():
            result.details = body_text.strip()[:500]

        return result
