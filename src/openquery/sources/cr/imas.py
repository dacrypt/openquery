"""IMAS source — Costa Rica social programs beneficiary lookup.

Queries the Instituto Mixto de Ayuda Social (IMAS) for beneficiary status.

Source: https://www.imas.go.cr/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.cr.imas import ImasResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

IMAS_URL = "https://www.imas.go.cr/"


@register
class ImasSource(BaseSource):
    """Query Costa Rica IMAS social programs by cedula."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="cr.imas",
            display_name="IMAS — Programas Sociales",
            description=(
                "Costa Rica IMAS: social programs beneficiary status by cedula"
            ),
            country="CR",
            url=IMAS_URL,
            supported_inputs=[DocumentType.CEDULA, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        cedula = input.extra.get("cedula", "") or input.document_number.strip()
        if not cedula:
            raise SourceError("cr.imas", "Cédula is required")
        return self._query(cedula=cedula, audit=input.audit)

    def _query(self, cedula: str, audit: bool = False) -> ImasResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("cr.imas", "cedula", cedula)

        with browser.page(IMAS_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "page_loaded")

                cedula_input = page.query_selector(
                    'input[name*="cedula"], input[id*="cedula"], '
                    'input[type="text"], input[name*="identificacion"]'
                )
                if cedula_input:
                    cedula_input.fill(cedula)
                    logger.info("Querying IMAS for cedula: %s", cedula)

                    submit_btn = page.query_selector(
                        'button[type="submit"], input[type="submit"], '
                        'button:has-text("Consultar"), button:has-text("Buscar")'
                    )
                    if submit_btn:
                        submit_btn.click()
                    else:
                        cedula_input.press("Enter")

                    page.wait_for_timeout(4000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, cedula)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("cr.imas", f"Query failed: {e}") from e

    def _parse_result(self, page, cedula: str) -> ImasResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        beneficiary_name = ""
        program_name = ""
        beneficiary_status = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if "nombre" in lower and ":" in stripped and not beneficiary_name:
                beneficiary_name = stripped.split(":", 1)[1].strip()
            elif "programa" in lower and ":" in stripped and not program_name:
                program_name = stripped.split(":", 1)[1].strip()
            elif "estado" in lower and ":" in stripped and not beneficiary_status:
                beneficiary_status = stripped.split(":", 1)[1].strip()

        return ImasResult(
            queried_at=datetime.now(),
            cedula=cedula,
            beneficiary_name=beneficiary_name,
            program_name=program_name,
            beneficiary_status=beneficiary_status,
            details=body_text.strip()[:500],
        )
