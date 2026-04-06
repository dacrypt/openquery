"""SOAT source — Peru mandatory vehicle insurance lookup (APESEG/SBS).

Queries APESEG for SOAT (mandatory insurance) validity by license plate.
Protected by CAPTCHA.

Flow:
1. Navigate to the APESEG SOAT consultation page
2. Enter license plate
3. Solve CAPTCHA
4. Submit and parse results
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pe.soat import SoatResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SOAT_URL = "https://www.apeseg.org.pe/consultas-soat/"


@register
class SoatSource(BaseSource):
    """Query Peru's APESEG for SOAT (mandatory insurance) by plate."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pe.soat",
            display_name="SOAT — Consulta APESEG/SBS",
            description="Peru mandatory vehicle insurance (SOAT) validity and insurer by plate",
            country="PE",
            url=SOAT_URL,
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=True,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.PLATE:
            raise SourceError(
                "pe.soat",
                f"Unsupported document type: {input.document_type}. Use PLATE.",
            )
        placa = input.document_number.strip()
        if not placa:
            raise SourceError("pe.soat", "Plate number is required.")
        return self._query(placa=placa, audit=input.audit)

    def _query(self, placa: str, audit: bool = False) -> SoatResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("pe.soat", "placa", placa)

        with browser.page(SOAT_URL, wait_until="commit") as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)

                plate_input = page.query_selector(
                    "input[name*='placa' i], input[id*='placa' i], "
                    "input[placeholder*='placa' i], input[name*='vehiculo' i], "
                    "input[type='text']"
                )
                if plate_input:
                    plate_input.fill(placa)
                    logger.info("Filled placa: %s", placa)

                if collector:
                    collector.screenshot(page, "form_filled")

                page.wait_for_timeout(2000)

                submit = page.query_selector(
                    "button[type='submit'], input[type='submit'], "
                    "button:has-text('Consultar'), button:has-text('Buscar')"
                )
                if submit:
                    submit.click()
                else:
                    page.keyboard.press("Enter")

                page.wait_for_timeout(4000)
                page.wait_for_selector(
                    "table, .result, #resultado, .soat-result, body",
                    timeout=20000,
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
                raise SourceError("pe.soat", f"Query failed: {e}") from e

    def _parse_result(self, page, placa: str) -> SoatResult:
        body_text = page.inner_text("body")
        result = SoatResult(placa=placa)
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
                    if "asegurador" in label_lower or "compan" in label_lower:
                        result.insurer = value
                    elif "vencimiento" in label_lower or "expir" in label_lower:
                        result.expiration_date = value
                    elif "estado" in label_lower or "vigencia" in label_lower:
                        result.soat_valid = "vigente" in value.lower() or "activo" in value.lower()

        if details:
            result.details = details

        # Fallback: body text patterns
        if not result.insurer:
            m = re.search(r"(?:Asegurador|Compan[ií]a)[:\s]+([^\n]+)", body_text, re.IGNORECASE)
            if m:
                result.insurer = m.group(1).strip()
        if not result.expiration_date:
            m = re.search(r"Vencimiento[:\s]+([^\n]+)", body_text, re.IGNORECASE)
            if m:
                result.expiration_date = m.group(1).strip()
        if not result.soat_valid:
            result.soat_valid = bool(re.search(r"VIGENTE|ACTIVO", body_text, re.IGNORECASE))

        return result
