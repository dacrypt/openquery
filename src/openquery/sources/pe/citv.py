"""CITV source — Peru vehicle technical inspection (MTC).

Queries MTC for vehicle technical inspection (CITV) status by license plate.
Protected by CAPTCHA.

Flow:
1. Navigate to the MTC CITV consultation page
2. Enter license plate
3. Solve CAPTCHA
4. Submit and parse results
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pe.citv import CitvResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CITV_URL = "https://rec.mtc.gob.pe/Citv/ArConsultaCitv"


@register
class CitvSource(BaseSource):
    """Query Peru's MTC for vehicle technical inspection (CITV) by plate."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pe.citv",
            display_name="CITV — Inspección Técnica Vehicular (MTC)",
            description="Peru vehicle technical inspection (CITV) validity and center by plate",
            country="PE",
            url=CITV_URL,
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=True,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.PLATE:
            raise SourceError(
                "pe.citv",
                f"Unsupported document type: {input.document_type}. Use PLATE.",
            )
        placa = input.document_number.strip()
        if not placa:
            raise SourceError("pe.citv", "Plate number is required.")
        return self._query(placa=placa, audit=input.audit)

    def _query(self, placa: str, audit: bool = False) -> CitvResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("pe.citv", "placa", placa)

        with browser.page(CITV_URL, wait_until="commit") as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)

                plate_input = page.query_selector(
                    "input[name*='placa' i], input[id*='placa' i], "
                    "input[placeholder*='placa' i], input[name*='Placa'], "
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
                    "table, .result, #resultado, .citv-result, body",
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
                raise SourceError("pe.citv", f"Query failed: {e}") from e

    def _parse_result(self, page, placa: str) -> CitvResult:
        body_text = page.inner_text("body")
        result = CitvResult(placa=placa)
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
                    if "centro" in label_lower or "planta" in label_lower:
                        result.inspection_center = value
                    elif "vencimiento" in label_lower or "vigencia" in label_lower:
                        result.expiration_date = value
                    elif "estado" in label_lower or "resultado" in label_lower:
                        val_lower = value.lower()
                        result.citv_valid = "aprobado" in val_lower or "vigente" in val_lower

        if details:
            result.details = details

        # Fallback: body text patterns
        if not result.inspection_center:
            m = re.search(
                r"(?:Centro|Planta)[:\s]+([^\n]+)", body_text, re.IGNORECASE
            )
            if m:
                result.inspection_center = m.group(1).strip()
        if not result.expiration_date:
            m = re.search(r"Vencimiento[:\s]+([^\n]+)", body_text, re.IGNORECASE)
            if m:
                result.expiration_date = m.group(1).strip()
        if not result.citv_valid:
            result.citv_valid = bool(
                re.search(r"APROBADO|VIGENTE", body_text, re.IGNORECASE)
            )

        return result
