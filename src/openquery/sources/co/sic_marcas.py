"""SIC Marcas source — Colombian trademark registry.

Queries the SIC (Superintendencia de Industria y Comercio) for
trademark registration and status information.

Source: https://www.sic.gov.co/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.sic_marcas import SicMarcasResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SIC_MARCAS_URL = "https://www.sic.gov.co/buscar-marca"


@register
class SicMarcasSource(BaseSource):
    """Query Colombian trademark registry (SIC)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.sic_marcas",
            display_name="SIC — Registro de Marcas",
            description="Colombian trademark registry: status, owner, and registration details (SIC)",  # noqa: E501
            country="CO",
            url=SIC_MARCAS_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (
            input.extra.get("trademark_name", "")
            or input.extra.get("name", "")
            or input.document_number
        ).strip()
        if not search_term:
            raise SourceError("co.sic_marcas", "Trademark name required (pass via extra.trademark_name or document_number)")  # noqa: E501
        return self._query(search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> SicMarcasResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.sic_marcas", "trademark", search_term)

        with browser.page(SIC_MARCAS_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(2000)

                search_input = page.locator(
                    'input[placeholder*="marca"], input[placeholder*="Marca"], '
                    'input[type="text"], #search, input[name*="search"]'
                ).first
                if search_input:
                    search_input.fill(search_term)
                    logger.info("Searching SIC Marcas for: %s", search_term)

                    submit_btn = page.locator('button[type="submit"], input[type="submit"], button:has-text("Buscar")').first  # noqa: E501
                    if submit_btn:
                        submit_btn.click()
                    else:
                        search_input.press("Enter")

                    page.wait_for_timeout(4000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_term)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("co.sic_marcas", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> SicMarcasResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = SicMarcasResult(queried_at=datetime.now(), search_term=search_term)

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if "marca" in lower and ":" in stripped and not result.trademark_name:
                result.trademark_name = stripped.split(":", 1)[1].strip()
            elif "titular" in lower and ":" in stripped and not result.owner:
                result.owner = stripped.split(":", 1)[1].strip()
            elif "estado" in lower and ":" in stripped and not result.status:
                result.status = stripped.split(":", 1)[1].strip()

        return result
