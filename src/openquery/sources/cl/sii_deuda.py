"""SII Deuda source — SII tax situation of third parties (Chile).

Queries the SII portal for the tax compliance status and debt indicators of a RUT.

Flow:
1. Navigate to the SII third-party tax situation lookup page
2. Enter the RUT
3. Submit and parse the tax status / debt indicators
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.cl.sii_deuda import SiiDeudaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SII_DEUDA_URL = "https://www.sii.cl/como_se_hace_para/situacion_trib_terceros.html"


@register
class SiiDeudaSource(BaseSource):
    """Query SII tax situation (debt indicators) for a Chilean RUT."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="cl.sii_deuda",
            display_name="SII — Situacion Tributaria de Terceros",
            description="SII tax compliance status and debt indicators for a Chilean RUT",
            country="CL",
            url=SII_DEUDA_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        rut = input.extra.get("rut", "") or input.document_number
        if not rut:
            raise SourceError("cl.sii_deuda", "RUT is required (pass via extra.rut)")
        return self._query(rut, audit=input.audit)

    def _query(self, rut: str, audit: bool = False) -> SiiDeudaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("cl.sii_deuda", "rut", rut)

        with browser.page(SII_DEUDA_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill RUT input
                rut_input = page.query_selector(
                    'input[name*="rut"], input[name*="RUT"], '
                    'input[placeholder*="12.345"], input[placeholder*="RUT"], '
                    'input.rut-form, input[type="text"]'
                )
                if not rut_input:
                    raise SourceError("cl.sii_deuda", "Could not find RUT input field")
                rut_input.fill(rut)
                logger.info("Filled RUT: %s", rut)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit = page.query_selector(
                    'input[name="Consultar"], input.button-azul, '
                    'button[type="submit"], input[type="submit"], '
                    "button:has-text('Consultar'), button:has-text('Buscar')"
                )
                if submit:
                    submit.click()
                else:
                    rut_input.press("Enter")

                page.wait_for_timeout(3000)
                page.wait_for_selector("body", timeout=15000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, rut)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("cl.sii_deuda", f"Query failed: {e}") from e

    def _parse_result(self, page, rut: str) -> SiiDeudaResult:
        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        result = SiiDeudaResult(rut=rut)

        # Parse tax status
        m = re.search(
            r"(?:situaci[oó]n\s*tributaria|estado\s*tributario|estado)[:\s]+([^\n]+)",
            body_text,
            re.IGNORECASE,
        )
        if m:
            result.tax_status = m.group(1).strip()

        # Determine has_debt from keywords
        debt_keywords = ["deuda", "mora", "adeuda", "pendiente", "impago"]
        no_debt_keywords = ["sin deuda", "al d[ií]a", "no registra", "sin mora"]

        has_no_debt = any(re.search(kw, body_lower) for kw in no_debt_keywords)
        has_debt = any(kw in body_lower for kw in debt_keywords)

        if has_no_debt:
            result.has_debt = False
        elif has_debt:
            result.has_debt = True

        # Parse individual debt indicators from the page
        indicators = re.findall(
            r"(?:indicador|alerta|observaci[oó]n)[:\s]+([^\n]+)",
            body_text,
            re.IGNORECASE,
        )
        result.debt_indicators = [i.strip() for i in indicators if i.strip()]

        # Parse table rows for structured details
        rows = page.query_selector_all("table tr, .resultado tr, .situacion tr")
        details: dict[str, str] = {}
        for row in rows:
            cells = row.query_selector_all("td, th")
            if len(cells) >= 2:
                key = (cells[0].inner_text() or "").strip()
                val = (cells[1].inner_text() or "").strip()
                if key and val:
                    details[key] = val
                    key_lower = key.lower()
                    if "situaci" in key_lower or "estado" in key_lower:
                        result.tax_status = result.tax_status or val

        result.details = details

        return result
