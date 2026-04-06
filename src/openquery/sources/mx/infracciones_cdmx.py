"""InfraccionesCdmx source — CDMX traffic infractions.

Queries the CDMX infracciones portal for traffic fines by plate.

Flow:
1. Navigate to infracciones.cdmx.gob.mx
2. Enter plate number
3. Submit and parse infractions list and amounts
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.mx.infracciones_cdmx import InfraccionesCdmxResult, InfraccionRecord
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

INFRACCIONES_URL = "https://infracciones.cdmx.gob.mx/"


@register
class InfraccionesCdmxSource(BaseSource):
    """Query CDMX traffic infractions by plate number."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="mx.infracciones_cdmx",
            display_name="Infracciones CDMX",
            description="CDMX traffic infractions: fines, amounts, and payment status by plate",
            country="MX",
            url=INFRACCIONES_URL,
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.PLATE:
            raise SourceError(
                "mx.infracciones_cdmx", f"Unsupported document type: {input.document_type}"
            )
        return self._query(input.document_number.upper().strip(), audit=input.audit)

    def _query(self, placa: str, audit: bool = False) -> InfraccionesCdmxResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("mx.infracciones_cdmx", "placa", placa)

        with browser.page(INFRACCIONES_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill plate field
                plate_input = page.query_selector(
                    'input[name*="placa"], input[name*="plate"], input[id*="placa"], '
                    'input[type="text"]'
                )
                if not plate_input:
                    raise SourceError("mx.infracciones_cdmx", "Could not find plate input field")
                plate_input.fill(placa)
                logger.info("Filled plate: %s", placa)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    "button:has-text('Consultar'), button:has-text('Buscar')"
                )
                if submit:
                    submit.click()
                else:
                    plate_input.press("Enter")

                page.wait_for_timeout(3000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, placa)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("mx.infracciones_cdmx", f"Query failed: {e}") from e

    def _parse_result(self, page, placa: str) -> InfraccionesCdmxResult:
        import re

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        result = InfraccionesCdmxResult(placa=placa)

        if "sin infracciones" in body_lower or "no se encontraron" in body_lower:
            result.details = "Sin infracciones registradas"
            return result

        # Parse total count
        count_match = re.search(r"(\d+)\s*infracci[oó]n(?:es)?", body_text, re.IGNORECASE)
        if count_match:
            result.total_infractions = int(count_match.group(1))

        # Parse total amount
        total_match = re.search(r"total[:\s]*\$\s*([\d,]+(?:\.\d{2})?)", body_text, re.IGNORECASE)
        if total_match:
            result.total_amount = f"${total_match.group(1)}"

        # Parse individual infraction rows from table rows
        rows = page.query_selector_all("table tr, .infraction-row, .resultado tr")
        for row in rows:
            try:
                cells = row.query_selector_all("td")
                if len(cells) >= 3:
                    texts = [c.inner_text().strip() for c in cells]
                    infraction = InfraccionRecord(
                        folio=texts[0] if len(texts) > 0 else "",
                        fecha=texts[1] if len(texts) > 1 else "",
                        descripcion=texts[2] if len(texts) > 2 else "",
                        monto=texts[3] if len(texts) > 3 else "",
                        estatus=texts[4] if len(texts) > 4 else "",
                    )
                    if infraction.folio or infraction.descripcion:
                        result.infractions.append(infraction)
            except Exception as e:
                logger.debug("Failed to parse row: %s", e)

        if not result.total_infractions and result.infractions:
            result.total_infractions = len(result.infractions)

        result.details = body_text[:500].strip()

        return result
