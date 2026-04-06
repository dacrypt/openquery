"""BANAVIH source — Venezuela housing savings (FAOV) lookup.

Queries the BANAVIH portal for FAOV contribution status by cedula.

Source: https://www.banavih.gob.ve/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ve.banavih import BanavihResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

BANAVIH_URL = "https://www.banavih.gob.ve/"


@register
class BanavihSource(BaseSource):
    """Query Venezuela BANAVIH FAOV housing savings by cedula."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ve.banavih",
            display_name="BANAVIH — Consulta FAOV",
            description=(
                "Venezuela BANAVIH housing savings: FAOV contribution status and employer by cedula"
            ),
            country="VE",
            url=BANAVIH_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        cedula = input.extra.get("cedula", "") or input.document_number.strip()
        if not cedula:
            raise SourceError("ve.banavih", "Cedula is required")
        return self._query(cedula=cedula, audit=input.audit)

    def _query(self, cedula: str, audit: bool = False) -> BanavihResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("ve.banavih", "cedula", cedula)

        with browser.page(BANAVIH_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "page_loaded")

                cedula_input = page.query_selector(
                    'input[name*="cedula"], input[name*="ci"], '
                    'input[id*="cedula"], input[id*="ci"], '
                    'input[placeholder*="cedula"], input[placeholder*="cédula"], '
                    'input[type="text"]'
                )
                if not cedula_input:
                    raise SourceError("ve.banavih", "Could not find cedula input field")

                cedula_input.fill(cedula)
                logger.info("Querying BANAVIH for cedula: %s", cedula)

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
                    cedula_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, cedula)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("ve.banavih", f"Query failed: {e}") from e

    def _parse_result(self, page, cedula: str) -> BanavihResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        contribution_status = ""
        employer = ""

        field_map = {
            "estado": "contribution_status",
            "estatus": "contribution_status",
            "aporte": "contribution_status",
            "cotización": "contribution_status",
            "patrono": "employer",
            "empleador": "employer",
            "empresa": "employer",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_map.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value:
                        if field == "contribution_status" and not contribution_status:
                            contribution_status = value
                        elif field == "employer" and not employer:
                            employer = value
                    break

        return BanavihResult(
            queried_at=datetime.now(),
            cedula=cedula,
            contribution_status=contribution_status,
            employer=employer,
            details=body_text.strip()[:500],
        )
