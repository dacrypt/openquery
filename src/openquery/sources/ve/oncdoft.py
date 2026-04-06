"""ONCDOFT source — Venezuela price regulation lookup.

Queries Venezuela SUNDDE (formerly ONCDOFT) for regulated product prices.
Browser-based, no CAPTCHA.

URL: https://www.sundde.gob.ve/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ve.oncdoft import VeOncdoftResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

ONCDOFT_URL = "https://www.sundde.gob.ve/"


@register
class VeOncdoftSource(BaseSource):
    """Query Venezuela SUNDDE/ONCDOFT regulated product prices."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ve.oncdoft",
            display_name="ONCDOFT/SUNDDE — Precios Regulados (VE)",
            description="Venezuela SUNDDE regulated product prices by product name",
            country="VE",
            url=ONCDOFT_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("product_name", "") or input.document_number
        if not search_term:
            raise SourceError("ve.oncdoft", "Product name is required")
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> VeOncdoftResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("ve.oncdoft", "product_name", search_term)

        with browser.page(ONCDOFT_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "page_loaded")

                search_input = page.query_selector(
                    "input[name*='buscar'], input[name*='search'], input[name*='producto'], "
                    "input[id*='buscar'], input[id*='search'], input[id*='producto'], "
                    "input[placeholder*='producto'], input[placeholder*='buscar'], "
                    "input[type='text'], input[type='search']"
                )
                if not search_input:
                    raise SourceError("ve.oncdoft", "Could not find search input field")

                search_input.fill(search_term)
                logger.info("Querying ONCDOFT for product: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    "button[type='submit'], input[type='submit'], "
                    "button:has-text('Buscar'), button:has-text('Consultar')"
                )
                if submit:
                    submit.click()
                else:
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
                raise SourceError("ve.oncdoft", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> VeOncdoftResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = VeOncdoftResult(queried_at=datetime.now(), search_term=search_term)

        field_patterns = {
            "producto": "product_name",
            "denominación": "product_name",
            "descripción": "product_name",
            "precio": "regulated_price",
            "monto": "regulated_price",
            "valor": "regulated_price",
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
                if len(values) >= 1 and not result.product_name:
                    result.product_name = values[0]
                if len(values) >= 2 and not result.regulated_price:
                    result.regulated_price = values[1]

        result.details = {"raw": body_text.strip()[:500]}
        return result
