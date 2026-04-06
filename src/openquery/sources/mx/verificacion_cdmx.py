"""VerificacionCdmx source — CDMX emissions verification status.

Queries SEDEMA for vehicle emissions verification hologram and exemption status.

Flow:
1. Navigate to SEDEMA verificacion vehicular portal
2. Enter plate number
3. Submit and parse hologram type and validity
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.mx.verificacion_cdmx import VerificacionCdmxResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

VERIFICACION_URL = "https://sedema.cdmx.gob.mx/programas/programa/verificacion-vehicular"


@register
class VerificacionCdmxSource(BaseSource):
    """Query CDMX emissions verification (verificacion vehicular) status."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="mx.verificacion_cdmx",
            display_name="Verificacion Vehicular CDMX — SEDEMA",
            description="CDMX emissions verification: hologram type, exemption status, validity",
            country="MX",
            url=VERIFICACION_URL,
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.PLATE:
            raise SourceError(
                "mx.verificacion_cdmx", f"Unsupported document type: {input.document_type}"
            )
        return self._query(input.document_number.upper().strip(), audit=input.audit)

    def _query(self, placa: str, audit: bool = False) -> VerificacionCdmxResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("mx.verificacion_cdmx", "placa", placa)

        with browser.page(VERIFICACION_URL) as page:
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
                    raise SourceError("mx.verificacion_cdmx", "Could not find plate input field")
                plate_input.fill(placa)
                logger.info("Filled plate: %s", placa)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    "button:has-text('Consultar'), button:has-text('Buscar'), "
                    "button:has-text('Verificar')"
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
                raise SourceError("mx.verificacion_cdmx", f"Query failed: {e}") from e

    def _parse_result(self, page, placa: str) -> VerificacionCdmxResult:
        import re

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        result = VerificacionCdmxResult(placa=placa)

        # Hologram type: 00, 0, 1, 2
        hologram_match = re.search(r"holograma\s*[:\s]*(\d{1,2})", body_text, re.IGNORECASE)
        if hologram_match:
            result.hologram_type = hologram_match.group(1)
        elif "00" in body_text:
            result.hologram_type = "00"
        elif "exento" in body_lower or "cero" in body_lower:
            result.hologram_type = "0"

        # Exemption status
        if "exento" in body_lower:
            result.exemption_status = "Exento"
        elif "no exento" in body_lower:
            result.exemption_status = "No exento"

        # Validity semester
        semester_match = re.search(
            r"(?:semestre|vigencia|periodo)[:\s]+([^\n]+)", body_text, re.IGNORECASE
        )
        if semester_match:
            result.validity_semester = semester_match.group(1).strip()

        result.details = body_text[:500].strip()

        return result
