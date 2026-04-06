"""Uruguay INE statistics portal source.

Queries Uruguay INE (Instituto Nacional de Estadística) for statistical indicators.
Browser-based or httpx, no CAPTCHA.

URL: https://www.ine.gub.uy/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.uy.ine import UyIneResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

INE_URL = "https://www.ine.gub.uy/"


@register
class UyIneSource(BaseSource):
    """Query Uruguay INE statistical indicators."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="uy.ine",
            display_name="INE — Estadísticas (UY)",
            description="Uruguay INE statistics portal: statistical indicators by query",
            country="UY",
            url=INE_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        indicator = input.extra.get("indicator", "") or input.document_number
        if not indicator:
            raise SourceError("uy.ine", "Indicator is required")
        return self._query(indicator.strip(), audit=input.audit)

    def _query(self, indicator: str, audit: bool = False) -> UyIneResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("uy.ine", "indicator", indicator)

        with browser.page(INE_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    "input[name*='indicador'], input[id*='indicador'], "
                    "input[name*='search'], input[name*='buscar'], input[type='text']"
                )
                if not search_input:
                    raise SourceError("uy.ine", "Could not find search input field")

                search_input.fill(indicator)
                logger.info("Filled indicator: %s", indicator)

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

                result = self._parse_result(page, indicator)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("uy.ine", f"Query failed: {e}") from e

    def _parse_result(self, page, indicator: str) -> UyIneResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = UyIneResult(queried_at=datetime.now(), indicator=indicator)

        field_patterns = {
            "valor": "value",
            "value": "value",
            "periodo": "period",
            "fecha": "period",
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
                if len(values) >= 1 and not result.value:
                    result.value = values[0]
                if len(values) >= 2 and not result.period:
                    result.period = values[1]

        return result
