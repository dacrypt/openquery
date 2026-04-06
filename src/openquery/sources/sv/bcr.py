"""El Salvador BCR economic indicators source.

Queries BCR (Banco Central de Reserva) for economic indicators
and exchange rate data. El Salvador uses USD as official currency
but BCR tracks economic indicators.

URL: https://www.bcr.gob.sv/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.sv.bcr import SvBcrResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

BCR_URL = "https://www.bcr.gob.sv/"
BCR_INDICADORES_URL = "https://www.bcr.gob.sv/bcrsite/?cat=1000&lang=es"


@register
class SvBcrSource(BaseSource):
    """Query El Salvador BCR for economic indicators."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="sv.bcr",
            display_name="BCR — Indicadores Económicos El Salvador",
            description=(
                "El Salvador BCR central bank: economic indicators, "
                "financial rates, and macroeconomic data"
            ),
            country="SV",
            url=BCR_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query BCR for economic indicator data."""
        indicator = input.extra.get("indicator", "") or input.document_number or "tipo_cambio"
        return self._query(indicator.strip(), audit=input.audit)

    def _query(self, indicator: str, audit: bool = False) -> SvBcrResult:
        """Full flow: launch browser, navigate to indicators, parse results."""
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("sv.bcr", "indicator", indicator)

        with browser.page(BCR_INDICADORES_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "indicators_page")

                result = self._parse_result(page, indicator)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("sv.bcr", f"Query failed: {e}") from e

    def _parse_result(self, page, indicator: str) -> SvBcrResult:
        """Parse economic indicator data from the page DOM."""
        from datetime import datetime

        body_text = page.inner_text("body")
        result = SvBcrResult(indicator=indicator, date=datetime.now().strftime("%Y-%m-%d"))
        details: dict[str, str] = {}

        indicator_lower = indicator.lower()

        for line in body_text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            lower = stripped.lower()

            if any(kw in lower for kw in [indicator_lower, "tipo de cambio", "tasa", "índice"]):
                if ":" in stripped:
                    key, _, val = stripped.partition(":")
                    val = val.strip()
                    if val and not result.value:
                        result.value = val

            if ":" in stripped:
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip()
                if key and val and len(key) < 80:
                    details[key] = val

        rows = page.query_selector_all("table tr")
        for row in rows:
            cells = row.query_selector_all("td")
            if len(cells) >= 2:
                label = (cells[0].inner_text() or "").strip().lower()
                value = (cells[1].inner_text() or "").strip()
                if indicator_lower in label and value and not result.value:
                    result.value = value

        result.details = details
        logger.info("BCR result — indicator=%s, value=%s", indicator, result.value)
        return result
