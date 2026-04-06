"""Fotocivicas source — CDMX photo enforcement fines.

Queries the CDMX fotocivicas portal for photo-enforced violations by plate.

Flow:
1. Navigate to tramites.cdmx.gob.mx/fotocivicas
2. Enter plate number
3. Submit and parse violations (speed cameras, red lights)
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.mx.fotocivicas import FotocivicasResult, FotocivicaViolation
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

FOTOCIVICAS_URL = "https://www.tramites.cdmx.gob.mx/fotocivicas/public/"


@register
class FotocivicasSource(BaseSource):
    """Query CDMX photo enforcement fines by plate number."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="mx.fotocivicas",
            display_name="Fotocivicas CDMX",
            description="CDMX photo enforcement fines: speed cameras and red light violations",
            country="MX",
            url=FOTOCIVICAS_URL,
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.PLATE:
            raise SourceError("mx.fotocivicas", f"Unsupported document type: {input.document_type}")
        return self._query(input.document_number.upper().strip(), audit=input.audit)

    def _query(self, placa: str, audit: bool = False) -> FotocivicasResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("mx.fotocivicas", "placa", placa)

        with browser.page(FOTOCIVICAS_URL) as page:
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
                    raise SourceError("mx.fotocivicas", "Could not find plate input field")
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
                raise SourceError("mx.fotocivicas", f"Query failed: {e}") from e

    def _parse_result(self, page, placa: str) -> FotocivicasResult:
        import re

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        result = FotocivicasResult(placa=placa)

        if (
            "sin infracciones" in body_lower
            or "no se encontraron" in body_lower
            or "sin multas" in body_lower
        ):
            result.details = "Sin fotocivicas registradas"
            return result

        # Parse total violations count
        count_match = re.search(
            r"(\d+)\s*(?:infracci[oó]n(?:es)?|multa[s]?|violaci[oó]n(?:es)?)",
            body_text,
            re.IGNORECASE,
        )
        if count_match:
            result.total_violations = int(count_match.group(1))

        # Parse total amount
        total_match = re.search(r"total[:\s]*\$\s*([\d,]+(?:\.\d{2})?)", body_text, re.IGNORECASE)
        if total_match:
            result.total_amount = f"${total_match.group(1)}"

        # Parse individual violation rows from table
        rows = page.query_selector_all("table tr, .violation-row, .resultado tr")
        for row in rows:
            try:
                cells = row.query_selector_all("td")
                if len(cells) >= 3:
                    texts = [c.inner_text().strip() for c in cells]
                    violation = FotocivicaViolation(
                        folio=texts[0] if len(texts) > 0 else "",
                        fecha=texts[1] if len(texts) > 1 else "",
                        tipo=texts[2] if len(texts) > 2 else "",
                        ubicacion=texts[3] if len(texts) > 3 else "",
                        monto=texts[4] if len(texts) > 4 else "",
                        estatus=texts[5] if len(texts) > 5 else "",
                    )
                    if violation.folio or violation.tipo:
                        result.violations.append(violation)
            except Exception as e:
                logger.debug("Failed to parse row: %s", e)

        if not result.total_violations and result.violations:
            result.total_violations = len(result.violations)

        result.details = body_text[:500].strip()

        return result
