"""Costa Rica INS marchamo source — vehicle insurance/tax lookup.

Queries INS marchamo portal for annual vehicle tax and SOA insurance status.
Browser-based, no CAPTCHA required.

Source: https://marchamo.ins-cr.com/marchamo/ConsultaMarchamo.aspx
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.cr.marchamo import CrMarchamoResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

MARCHAMO_URL = "https://marchamo.ins-cr.com/marchamo/ConsultaMarchamo.aspx"


@register
class CrMarchamoSource(BaseSource):
    """Query Costa Rica INS marchamo portal by plate."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="cr.marchamo",
            display_name="INS — Consulta de Marchamo",
            description=(
                "Costa Rica annual vehicle tax (marchamo) and SOA insurance status "
                "(Instituto Nacional de Seguros)"
            ),
            country="CR",
            url=MARCHAMO_URL,
            supported_inputs=[DocumentType.PLATE, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        placa = input.extra.get("placa", "") or input.document_number
        if not placa:
            raise SourceError("cr.marchamo", "Placa is required")
        return self._query(placa.strip().upper(), audit=input.audit)

    def _query(self, placa: str, audit: bool = False) -> CrMarchamoResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("cr.marchamo", "placa", placa)

        with browser.page(MARCHAMO_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                placa_input = page.query_selector(
                    '#txtPlaca, input[name="txtPlaca"], #txtplaca, input[name="txtplaca"]'
                )
                if not placa_input:
                    raise SourceError("cr.marchamo", "Could not find plate input field")

                placa_input.fill(placa)
                logger.info("Filled placa: %s", placa)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    '#btnConsultar, input[name="btnConsultar"], '
                    '#btnBuscar, input[name="btnBuscar"]'
                )
                if submit:
                    submit.click()
                else:
                    placa_input.press("Enter")

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
                raise SourceError("cr.marchamo", f"Query failed: {e}") from e

    def _parse_result(self, page, placa: str) -> CrMarchamoResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        result = CrMarchamoResult(
            queried_at=datetime.now(),
            placa=placa,
        )

        field_patterns = {
            "monto": "marchamo_amount",
            "total a pagar": "marchamo_amount",
            "vencimiento": "marchamo_expiry",
            "fecha de vencimiento": "marchamo_expiry",
            "seguro": "insurance_status",
            "soa": "insurance_status",
            "estado del seguro": "insurance_status",
            "descripción": "vehicle_description",
            "vehículo": "vehicle_description",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_patterns.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value:
                        setattr(result, field, value)
                    break

        result.details = body_text.strip()[:500]

        return result
