"""MDT source — Ecuador Ministerio del Trabajo labor consultation.

Queries Ecuador's Ministerio del Trabajo for labor registration,
employer data, and contract status by cedula or RUC.

Flow:
1. Navigate to the MDT consultation page
2. Enter cedula or RUC
3. Submit and parse result

Source: https://www.trabajo.gob.ec/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ec.mdt import MdtResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

MDT_URL = "https://www.trabajo.gob.ec/"


@register
class MdtSource(BaseSource):
    """Query Ecuador labor registration from Ministerio del Trabajo."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ec.mdt",
            display_name="MDT — Ministerio del Trabajo",
            description=(
                "Ecuador labor registration and contract status from Ministerio del Trabajo"
            ),
            country="EC",
            url=MDT_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CEDULA:
            raise SourceError("ec.mdt", f"Only cedula supported, got: {input.document_type}")

        search_value = input.document_number.strip()
        if not search_value:
            raise SourceError("ec.mdt", "Cedula or RUC is required")

        return self._query(search_value, audit=input.audit)

    def _query(self, search_value: str, audit: bool = False) -> MdtResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("ec.mdt", "cedula", search_value)

        with browser.page(MDT_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill cedula/RUC input
                doc_input = page.query_selector(
                    'input[id*="cedula"], input[name*="cedula"], '
                    'input[id*="ruc"], input[name*="ruc"], '
                    'input[id*="identificacion"], input[name*="identificacion"], '
                    'input[type="text"]'
                )
                if not doc_input:
                    raise SourceError("ec.mdt", "Could not find document input field")

                doc_input.fill(search_value)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="consultar"], button[id*="buscar"], '
                    'button:has-text("Consultar"), button:has-text("Buscar")'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    doc_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_value)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("ec.mdt", f"Query failed: {e}") from e

    def _parse_result(self, page, search_value: str) -> MdtResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        employer_name = ""
        labor_status = ""
        contract_type = ""
        details: dict[str, str] = {}

        for line in body_text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            lower = stripped.lower()
            if (
                "empleador" in lower or "empresa" in lower or "patron" in lower
            ) and ":" in stripped:
                employer_name = stripped.split(":", 1)[1].strip()
            elif (
                "estado" in lower or "situacion" in lower or "situación" in lower
            ) and ":" in stripped:
                labor_status = stripped.split(":", 1)[1].strip()
            elif ("contrato" in lower or "tipo" in lower) and ":" in stripped:
                contract_type = stripped.split(":", 1)[1].strip()
            elif ":" in stripped:
                key, _, val = stripped.partition(":")
                if key.strip() and val.strip():
                    details[key.strip()] = val.strip()

        return MdtResult(
            queried_at=datetime.now(),
            search_value=search_value,
            employer_name=employer_name,
            labor_status=labor_status,
            contract_type=contract_type,
            details=details,
        )
