"""SII Tasacion source — Vehicle tax valuation (Chile).

Queries the SII public vehicle portal for the fiscal tasacion (tax valuation)
used to calculate the permiso de circulacion.

Flow:
1. Navigate to the SII vehiculos public portal
2. Enter the plate number
3. Submit and parse tasacion value and vehicle description
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.cl.sii_tasacion import SiiTasacionResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SII_TASACION_URL = "https://www4.sii.cl/vehiculospubui/"


@register
class SiiTasacionSource(BaseSource):
    """Query SII for vehicle tax valuation (tasacion fiscal) by plate."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="cl.sii_tasacion",
            display_name="SII — Tasacion Fiscal Vehicular",
            description=(
                "Vehicle fiscal tax valuation from Chile's SII used for permiso de circulacion"
            ),
            country="CL",
            url=SII_TASACION_URL,
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        plate = input.document_number
        if not plate:
            raise SourceError("cl.sii_tasacion", "Plate number is required")
        return self._query(plate, audit=input.audit)

    def _query(self, plate: str, audit: bool = False) -> SiiTasacionResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("cl.sii_tasacion", "plate", plate)

        with browser.page(SII_TASACION_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill plate input
                plate_input = page.query_selector(
                    'input[name*="placa"], input[name*="Placa"], '
                    'input[placeholder*="placa"], input[placeholder*="Patente"], '
                    'input[name*="patente"], input[id*="patente"], '
                    'input[id*="placa"], input[type="text"]'
                )
                if not plate_input:
                    raise SourceError("cl.sii_tasacion", "Could not find plate input field")
                plate_input.fill(plate)
                logger.info("Filled plate: %s", plate)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit = page.query_selector(
                    'input[type="submit"], button[type="submit"], '
                    "button:has-text('Consultar'), button:has-text('Buscar'), "
                    "button:has-text('Ver'), input[value='Consultar']"
                )
                if submit:
                    submit.click()
                else:
                    plate_input.press("Enter")

                page.wait_for_timeout(3000)
                page.wait_for_selector("body", timeout=15000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, plate)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("cl.sii_tasacion", f"Query failed: {e}") from e

    def _parse_result(self, page, plate: str) -> SiiTasacionResult:
        body_text = page.inner_text("body")

        result = SiiTasacionResult(placa=plate)

        # Parse tasacion value — look for currency amounts
        m = re.search(
            r"(?:tasaci[oó]n|valor\s*fiscal|avaluo|valor)[:\s]+\$?\s*([\d.,]+)",
            body_text,
            re.IGNORECASE,
        )
        if m:
            result.tasacion_value = m.group(1).strip()

        # Parse vehicle description
        m = re.search(
            r"(?:descripci[oó]n|veh[ií]culo|marca|modelo)[:\s]+([^\n]+)",
            body_text,
            re.IGNORECASE,
        )
        if m:
            result.vehicle_description = m.group(1).strip()

        # Parse table rows for structured details
        rows = page.query_selector_all("table tr, .resultado tr, .tasacion tr")
        details: dict[str, str] = {}
        for row in rows:
            cells = row.query_selector_all("td, th")
            if len(cells) >= 2:
                key = (cells[0].inner_text() or "").strip()
                val = (cells[1].inner_text() or "").strip()
                if key and val:
                    details[key] = val
                    key_lower = key.lower()
                    if "tasaci" in key_lower or "valor" in key_lower or "avaluo" in key_lower:
                        result.tasacion_value = result.tasacion_value or val
                    if (
                        "descripci" in key_lower
                        or "marca" in key_lower
                        or "modelo" in key_lower
                        or "veh" in key_lower
                    ):
                        result.vehicle_description = result.vehicle_description or val

        result.details = details

        return result
