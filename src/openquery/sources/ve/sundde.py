"""SUNDDE source — Venezuela price regulation.

Queries the SUNDDE (Superintendencia Nacional para la Defensa de los
Derechos Socioeconómicos) for regulated product prices.

Source: https://www.sundde.gob.ve/
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ve.sundde import SunddeResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SUNDDE_URL = "https://www.sundde.gob.ve/"


@register
class SunddeSource(BaseSource):
    """Query SUNDDE Venezuelan price regulation database."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ve.sundde",
            display_name="SUNDDE — Regulación de Precios",
            description="SUNDDE Venezuelan price regulation: regulated product prices and enforcement",  # noqa: E501
            country="VE",
            url=SUNDDE_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (
            input.extra.get("product", "")
            or input.extra.get("product_name", "")
            or input.document_number
        ).strip()
        if not search_term:
            raise SourceError("ve.sundde", "Product name required (pass via extra.product or document_number)")  # noqa: E501
        return self._query(search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> SunddeResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("ve.sundde", "product", search_term)

        with browser.page(SUNDDE_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(2000)

                search_input = page.locator(
                    'input[type="search"], input[placeholder*="producto"], '
                    'input[placeholder*="Producto"], input[type="text"]'
                ).first
                if search_input:
                    search_input.fill(search_term)
                    logger.info("Searching SUNDDE for: %s", search_term)
                    search_input.press("Enter")
                    page.wait_for_timeout(3000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_term)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("ve.sundde", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> SunddeResult:
        body_text = page.inner_text("body")
        result = SunddeResult(queried_at=datetime.now(), search_term=search_term)

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if "producto" in lower and ":" in stripped and not result.product_name:
                result.product_name = stripped.split(":", 1)[1].strip()
            elif "precio" in lower and ":" in stripped and not result.regulated_price:
                result.regulated_price = stripped.split(":", 1)[1].strip()

        return result
