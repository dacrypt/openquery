"""Uruguay BSE mandatory vehicle insurance source.

Queries Uruguay BSE (Banco de Seguros del Estado) for vehicle SOA insurance status.
Browser-based, no CAPTCHA.

URL: https://www.bse.com.uy/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.uy.bse import UyBseResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

BSE_URL = "https://www.bse.com.uy/"


@register
class UyBseSource(BaseSource):
    """Query Uruguay BSE mandatory vehicle SOA insurance status."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="uy.bse",
            display_name="BSE — Seguro Obligatorio (UY)",
            description="Uruguay BSE: mandatory vehicle SOA insurance status by license plate",
            country="UY",
            url=BSE_URL,
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        placa = input.document_number.strip()
        if not placa:
            raise SourceError("uy.bse", "License plate is required")
        return self._query(placa, audit=input.audit)

    def _query(self, placa: str, audit: bool = False) -> UyBseResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("uy.bse", "placa", placa)

        with browser.page(BSE_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    "input[name*='matricula'], input[id*='matricula'], "
                    "input[name*='placa'], input[name*='patente'], input[type='text']"
                )
                if not search_input:
                    raise SourceError("uy.bse", "Could not find plate input field")

                search_input.fill(placa)
                logger.info("Filled plate: %s", placa)

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

                result = self._parse_result(page, placa)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("uy.bse", f"Query failed: {e}") from e

    def _parse_result(self, page, placa: str) -> UyBseResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = UyBseResult(queried_at=datetime.now(), placa=placa)

        field_patterns = {
            "estado": "insurance_status",
            "vigencia": "policy_valid",
            "poliza": "policy_valid",
            "vencimiento": "policy_valid",
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
                if len(values) >= 1 and not result.insurance_status:
                    result.insurance_status = values[0]
                if len(values) >= 2 and not result.policy_valid:
                    result.policy_valid = values[1]

        return result
