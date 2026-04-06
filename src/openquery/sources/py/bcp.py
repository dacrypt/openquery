"""Paraguay BCP central bank exchange rates source.

Queries Paraguay BCP (Banco Central del Paraguay) for PYG/USD exchange rate.
Browser-based scraping of the BCP cotizacion page.

URL: https://www.bcp.gov.py/webapps/web/cotizacion/monedas
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.py.bcp import PyBcpResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

BCP_URL = "https://www.bcp.gov.py/webapps/web/cotizacion/monedas"


@register
class PyBcpSource(BaseSource):
    """Query Paraguay BCP central bank PYG/USD exchange rate."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="py.bcp",
            display_name="BCP — Tipo de Cambio (PY)",
            description="Paraguay BCP central bank: PYG/USD exchange rate",
            country="PY",
            url=BCP_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        return self._query(audit=input.audit)

    def _query(self, audit: bool = False) -> PyBcpResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("py.bcp", "query", "cotizacion")

        with browser.page(BCP_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "loaded")

                result = self._parse_result(page)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("py.bcp", f"Query failed: {e}") from e

    def _parse_result(self, page) -> PyBcpResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = PyBcpResult(queried_at=datetime.now())

        # Look for USD/PYG rate in table rows
        rows = page.query_selector_all("table tr")
        for row in rows:
            cells = row.query_selector_all("td")
            if not cells:
                continue
            values = [(c.inner_text() or "").strip() for c in cells]
            row_text = " ".join(values).upper()
            if "USD" in row_text or "DOLAR" in row_text:
                if len(values) >= 2:
                    result.usd_rate = values[-1]
                    if len(values) >= 1:
                        result.date = values[0] if len(values) >= 3 else ""
                break

        # Fallback: parse from body text
        if not result.usd_rate:
            for line in body_text.split("\n"):
                stripped = line.strip()
                lower = stripped.lower()
                if ("usd" in lower or "dolar" in lower) and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value:
                        result.usd_rate = value
                        break

        return result
