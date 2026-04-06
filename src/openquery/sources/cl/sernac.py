"""SERNAC source — Chile consumer complaints portal.

Queries Chile's SERNAC for consumer complaint statistics by company name.

Flow:
1. Navigate to the SERNAC complaints portal
2. Enter company name
3. Submit and parse complaint counts and resolution rates

Source: https://www.sernac.cl/portal/619/w3-propertyvalue-62498.html
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.cl.sernac import SernacResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SERNAC_URL = "https://www.sernac.cl/portal/619/w3-propertyvalue-62498.html"


@register
class SernacSource(BaseSource):
    """Query Chile's SERNAC consumer complaints portal."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="cl.sernac",
            display_name="SERNAC — Servicio Nacional del Consumidor",
            description="Chile consumer complaints: total complaints and resolution rates by company",
            country="CL",
            url=SERNAC_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CUSTOM:
            raise SourceError("cl.sernac", f"Unsupported input type: {input.document_type}")

        company = input.extra.get("company", "").strip()
        if not company:
            raise SourceError("cl.sernac", "Must provide extra['company'] (company name)")

        return self._query(company=company, audit=input.audit)

    def _query(self, company: str, audit: bool = False) -> SernacResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("cl.sernac", "empresa", company)

        with browser.page(SERNAC_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[id*="empresa"], input[name*="empresa"], '
                    'input[id*="proveedor"], input[name*="proveedor"], '
                    'input[placeholder*="empresa" i], input[type="text"]'
                )
                if search_input:
                    search_input.fill(company)
                    logger.info("Filled company name: %s", company)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button:has-text("Buscar"), button:has-text("Consultar")'
                )
                if submit:
                    submit.click()
                else:
                    page.keyboard.press("Enter")

                page.wait_for_timeout(4000)
                page.wait_for_selector("body", timeout=15000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, company)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("cl.sernac", f"Query failed: {e}") from e

    def _parse_result(self, page, company: str) -> SernacResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = SernacResult(queried_at=datetime.now(), company_name=company)
        details: dict = {}

        rows = page.query_selector_all("table tr, .result tr")
        for row in rows:
            cells = row.query_selector_all("td, th")
            if len(cells) >= 2:
                label = (cells[0].inner_text() or "").strip()
                value = (cells[1].inner_text() or "").strip()
                if label and value:
                    details[label] = value
                    label_lower = label.lower()
                    if "reclamo" in label_lower or "total" in label_lower:
                        result.total_complaints = value
                    elif "resoluci" in label_lower or "tasa" in label_lower:
                        result.resolution_rate = value

        if details:
            result.details = details

        # Fallback: body text scan
        if not result.total_complaints:
            for line in body_text.split("\n"):
                stripped = line.strip()
                lower = stripped.lower()
                if ("reclamo" in lower or "total" in lower) and ":" in stripped:
                    result.total_complaints = stripped.split(":", 1)[1].strip()
                elif ("resoluci" in lower or "tasa" in lower) and ":" in stripped and not result.resolution_rate:
                    result.resolution_rate = stripped.split(":", 1)[1].strip()

        return result
