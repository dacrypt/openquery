"""SAT Lima source — Peru SAT Lima vehicle taxes and papeletas.

Queries SAT Lima for pending papeletas (tickets) and vehicle tax status by plate.

Flow:
1. Navigate to the SAT Lima papeletas consultation page
2. Enter license plate
3. Submit and parse results
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pe.sat_lima import SatLimaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SAT_LIMA_URL = (
    "https://www.sat.gob.pe/WebSiteV9/TributosMultas/Papeletas/ConsultasPapeletas"
)


@register
class SatLimaSource(BaseSource):
    """Query Peru's SAT Lima for vehicle papeletas and tax status by plate."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pe.sat_lima",
            display_name="SAT Lima — Papeletas y Tributos Vehiculares",
            description="Peru SAT Lima pending tickets (papeletas) and vehicle tax status by plate",
            country="PE",
            url=SAT_LIMA_URL,
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.PLATE:
            raise SourceError(
                "pe.sat_lima",
                f"Unsupported document type: {input.document_type}. Use PLATE.",
            )
        placa = input.document_number.strip()
        if not placa:
            raise SourceError("pe.sat_lima", "Plate number is required.")
        return self._query(placa=placa, audit=input.audit)

    def _query(self, placa: str, audit: bool = False) -> SatLimaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("pe.sat_lima", "placa", placa)

        with browser.page(SAT_LIMA_URL, wait_until="commit") as page:
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
                    "table, .result, #resultado, .papeletas, body",
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
                raise SourceError("pe.sat_lima", f"Query failed: {e}") from e

    def _parse_result(self, page, placa: str) -> SatLimaResult:
        body_text = page.inner_text("body")
        result = SatLimaResult(placa=placa)
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
                    if "total" in label_lower and "monto" in label_lower:
                        result.total_amount = value
                    elif "impuesto" in label_lower or "tributo" in label_lower:
                        result.tax_status = value

        if details:
            result.details = details

        papeleta_rows = page.query_selector_all("table.papeletas tr, .papeletas tr, table tr")
        count = 0
        for row in papeleta_rows:
            cells = row.query_selector_all("td")
            if cells:
                count += 1
        if count > 0:
            result.total_papeletas = count

        # Fallback: body text patterns
        m = re.search(r"Total[:\s]+(S/\.?\s*[\d,\.]+)", body_text, re.IGNORECASE)
        if m and not result.total_amount:
            result.total_amount = m.group(1).strip()

        m = re.search(r"(?:Papeletas|Infracciones)[:\s]+(\d+)", body_text, re.IGNORECASE)
        if m:
            result.total_papeletas = int(m.group(1))

        m = re.search(r"(?:Impuesto|Tributo)[:\s]+([^\n]+)", body_text, re.IGNORECASE)
        if m and not result.tax_status:
            result.tax_status = m.group(1).strip()

        return result
