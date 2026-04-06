"""SUTRAN source — Peru traffic infraction record by plate.

Queries SUTRAN for vehicle traffic infraction records by license plate.
Protected by CAPTCHA.

Flow:
1. Navigate to the SUTRAN infraction record page
2. Enter license plate
3. Solve CAPTCHA
4. Submit and parse results
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pe.sutran import SutranInfraction, SutranResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SUTRAN_URL = "https://www.sutran.gob.pe/consultas/record-de-infracciones/record-de-infracciones/"


@register
class SutranSource(BaseSource):
    """Query Peru's SUTRAN traffic infraction record by plate."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pe.sutran",
            display_name="SUTRAN — Record de Infracciones",
            description="Peru traffic infraction record by license plate",
            country="PE",
            url=SUTRAN_URL,
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=True,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.PLATE:
            raise SourceError(
                "pe.sutran",
                f"Unsupported document type: {input.document_type}. Use PLATE.",
            )
        placa = input.document_number.strip()
        if not placa:
            raise SourceError("pe.sutran", "Plate number is required.")
        return self._query(placa=placa, audit=input.audit)

    def _query(self, placa: str, audit: bool = False) -> SutranResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("pe.sutran", "placa", placa)

        with browser.page(SUTRAN_URL, wait_until="commit") as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)

                plate_input = page.query_selector(
                    "input[name*='placa' i], input[id*='placa' i], "
                    "input[placeholder*='placa' i], input[type='text']"
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
                    "table, .result, #resultado, .infracciones, body",
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
                raise SourceError("pe.sutran", f"Query failed: {e}") from e

    def _parse_result(self, page, placa: str) -> SutranResult:
        body_text = page.inner_text("body")
        result = SutranResult(placa=placa)
        infractions: list[SutranInfraction] = []

        rows = page.query_selector_all("table tr")
        for row in rows:
            cells = row.query_selector_all("td")
            if len(cells) >= 3:
                infraction = SutranInfraction(
                    type=(cells[0].inner_text() or "").strip(),
                    date=(cells[1].inner_text() or "").strip() if len(cells) > 1 else "",
                    amount=(cells[2].inner_text() or "").strip() if len(cells) > 2 else "",
                    status=(cells[3].inner_text() or "").strip() if len(cells) > 3 else "",
                )
                if infraction.type:
                    infractions.append(infraction)

        if infractions:
            result.infractions = infractions
            result.total_infractions = len(infractions)

        m = re.search(r"Total[:\s]+(\d+)", body_text, re.IGNORECASE)
        if m:
            result.total_infractions = int(m.group(1))

        return result
