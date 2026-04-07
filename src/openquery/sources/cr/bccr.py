"""BCCR source — Costa Rica central bank economic indicators.

Queries the Banco Central de Costa Rica (BCCR) for exchange rates and
economic indicators.

Source: https://gee.bccr.fi.cr/indicadoreseconomicos/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.cr.bccr import BccrResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

BCCR_URL = "https://gee.bccr.fi.cr/indicadoreseconomicos/"


@register
class BccrSource(BaseSource):
    """Query Costa Rica BCCR economic indicators."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="cr.bccr",
            display_name="BCCR — Indicadores Económicos",
            description=(
                "Costa Rica BCCR: exchange rates and economic indicators by indicator code"
            ),
            country="CR",
            url=BCCR_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        indicator = input.extra.get("indicator", "") or input.document_number.strip()
        if not indicator:
            raise SourceError("cr.bccr", "Indicator code or name is required")
        return self._query(indicator=indicator, audit=input.audit)

    def _query(self, indicator: str, audit: bool = False) -> BccrResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("cr.bccr", "indicator", indicator)

        with browser.page(BCCR_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "page_loaded")

                search_input = page.query_selector(
                    'input[name*="indicador"], input[id*="indicador"], '
                    'input[type="search"], input[type="text"], '
                    'input[placeholder*="indicador"], input[name*="codigo"]'
                )
                if search_input:
                    search_input.fill(indicator)
                    logger.info("Querying BCCR for indicator: %s", indicator)

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

                result = self._parse_result(page, indicator)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("cr.bccr", f"Query failed: {e}") from e

    def _parse_result(self, page, indicator: str) -> BccrResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        indicator_name = ""
        value = ""
        period = ""
        unit = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if any(kw in lower for kw in ["indicador", "descripción"]) and ":" in stripped and not indicator_name:  # noqa: E501
                indicator_name = stripped.split(":", 1)[1].strip()
            elif any(kw in lower for kw in ["valor", "tipo de cambio", "monto"]) and ":" in stripped and not value:  # noqa: E501
                value = stripped.split(":", 1)[1].strip()
            elif any(kw in lower for kw in ["período", "fecha", "año"]) and ":" in stripped and not period:  # noqa: E501
                period = stripped.split(":", 1)[1].strip()
            elif any(kw in lower for kw in ["unidad", "moneda"]) and ":" in stripped and not unit:
                unit = stripped.split(":", 1)[1].strip()

        return BccrResult(
            queried_at=datetime.now(),
            indicator=indicator,
            indicator_name=indicator_name,
            value=value,
            period=period,
            unit=unit,
            details=body_text.strip()[:500],
        )
