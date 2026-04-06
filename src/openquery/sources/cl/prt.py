"""PRT source — Vehicle technical inspection status (Chile).

Queries the PRT portal for the Revision Tecnica (RT) status of a vehicle plate.

Flow:
1. Navigate to the PRT RT lookup page
2. Enter the plate number
3. Submit and parse RT validity, expiration date, last result, and plant
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.cl.prt import PrtResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

PRT_URL = "https://www.prt.cl/Paginas/RevisionTecnica.aspx"


@register
class PrtSource(BaseSource):
    """Query PRT for vehicle technical inspection (Revision Tecnica) status by plate."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="cl.prt",
            display_name="PRT — Revision Tecnica Vehicular",
            description=(
                "Vehicle technical inspection (RT) status and validity from Chile's PRT portal"
            ),
            country="CL",
            url=PRT_URL,
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        plate = input.document_number
        if not plate:
            raise SourceError("cl.prt", "Plate number is required")
        return self._query(plate, audit=input.audit)

    def _query(self, plate: str, audit: bool = False) -> PrtResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("cl.prt", "plate", plate)

        with browser.page(PRT_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill plate input
                plate_input = page.query_selector(
                    'input[name*="placa"], input[name*="Placa"], '
                    'input[placeholder*="placa"], input[placeholder*="Patente"], '
                    'input[name*="patente"], input[id*="placa"], '
                    'input[id*="Patente"], input[type="text"]'
                )
                if not plate_input:
                    raise SourceError("cl.prt", "Could not find plate input field")
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
                raise SourceError("cl.prt", f"Query failed: {e}") from e

    def _parse_result(self, page, plate: str) -> PrtResult:
        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        result = PrtResult(placa=plate)

        # Parse expiration date
        m = re.search(
            r"(?:vencimiento|vigencia|expira|v[aá]lido\s+hasta)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})",
            body_text,
            re.IGNORECASE,
        )
        if m:
            result.expiration_date = m.group(1).strip()

        # Parse last inspection result
        m = re.search(
            r"(?:resultado|ultimo\s+resultado|[uú]ltima\s+inspecci[oó]n)[:\s]+([^\n]+)",
            body_text,
            re.IGNORECASE,
        )
        if m:
            result.last_result = m.group(1).strip()

        # Parse plant
        m = re.search(
            r"(?:planta|establecimiento|taller)[:\s]+([^\n]+)",
            body_text,
            re.IGNORECASE,
        )
        if m:
            result.inspection_plant = m.group(1).strip()

        # Determine RT validity
        valid_keywords = ["vigente", "aprobada", "aprobado", "al d[ií]a", "v[aá]lida"]
        invalid_keywords = ["vencida", "vencido", "rechazada", "rechazado", "no vigente", "expirada"]  # noqa: E501

        has_valid = any(re.search(kw, body_lower) for kw in valid_keywords)
        has_invalid = any(re.search(kw, body_lower) for kw in invalid_keywords)

        if has_valid and not has_invalid:
            result.rt_valid = True
        elif has_invalid:
            result.rt_valid = False

        # Parse table rows for structured details
        rows = page.query_selector_all("table tr, .resultado tr, .revision tr")
        details: dict[str, str] = {}
        for row in rows:
            cells = row.query_selector_all("td, th")
            if len(cells) >= 2:
                key = (cells[0].inner_text() or "").strip()
                val = (cells[1].inner_text() or "").strip()
                if key and val:
                    details[key] = val
                    key_lower = key.lower()
                    if "planta" in key_lower or "establecimiento" in key_lower:
                        result.inspection_plant = result.inspection_plant or val
                    if "resultado" in key_lower:
                        result.last_result = result.last_result or val
                    if "vencimiento" in key_lower or "vigencia" in key_lower:
                        result.expiration_date = result.expiration_date or val

        result.details = details

        return result
