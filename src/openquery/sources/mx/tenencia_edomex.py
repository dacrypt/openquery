"""TenenciaEdomex source — Estado de Mexico vehicle tax (tenencia).

Queries the SFPYA portal for vehicle tenencia payment status by plate.
The portal uses a CAPTCHA.

Flow:
1. Navigate to the SFPYA tenencia portal
2. Enter plate and solve CAPTCHA
3. Submit and parse tenencia amount and payment status
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.mx.tenencia_edomex import TenenciaEdomexResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

TENENCIA_URL = (
    "https://sfpya.edomexico.gob.mx/controlv/faces/tramiteselectronicos/cv/"
    "portalPublico/ConsultaVigenciaPlaca.xhtml"
)


@register
class TenenciaEdomexSource(BaseSource):
    """Query Estado de Mexico vehicle tenencia tax status."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="mx.tenencia_edomex",
            display_name="Tenencia Edomex — SFPYA",
            description="Estado de Mexico vehicle tenencia tax: payment status and amount due",
            country="MX",
            url=TENENCIA_URL,
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=True,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.PLATE:
            raise SourceError(
                "mx.tenencia_edomex", f"Unsupported document type: {input.document_type}"
            )
        return self._query(input.document_number.upper().strip(), audit=input.audit)

    def _query(self, placa: str, audit: bool = False) -> TenenciaEdomexResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("mx.tenencia_edomex", "placa", placa)

        with browser.page(TENENCIA_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill plate field
                plate_input = page.query_selector(
                    'input[name*="placa"], input[name*="plate"], input[type="text"]'
                )
                if not plate_input:
                    raise SourceError("mx.tenencia_edomex", "Could not find plate input field")
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
                raise SourceError("mx.tenencia_edomex", f"Query failed: {e}") from e

    def _parse_result(self, page, placa: str) -> TenenciaEdomexResult:
        import re

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        result = TenenciaEdomexResult(placa=placa)

        # Payment status
        if "pagado" in body_lower:
            result.payment_status = "Pagado"
        elif "pendiente" in body_lower or "adeudo" in body_lower:
            result.payment_status = "Pendiente"
        elif "no encontrado" in body_lower or "no existe" in body_lower:
            result.payment_status = "No encontrado"

        # Tenencia amount
        amount_match = re.search(r"\$\s*([\d,]+(?:\.\d{2})?)", body_text)
        if amount_match:
            result.tenencia_amount = f"${amount_match.group(1)}"

        # Vehicle description
        vehicle_match = re.search(
            r"(?:veh[ií]culo|descripci[oó]n)[:\s]+([^\n]+)", body_text, re.IGNORECASE
        )
        if vehicle_match:
            result.vehicle_description = vehicle_match.group(1).strip()

        # Store full body as details fallback
        result.details = body_text[:500].strip()

        return result
