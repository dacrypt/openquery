"""Guatemala SAT vehicle source — circulation tax (calcomania).

Queries Guatemala's SAT (Superintendencia de Administración Tributaria)
for vehicle circulation tax payment status by plate and NIT.

Flow:
1. Navigate to SAT calcomania portal
2. Enter plate number and NIT
3. Submit and parse tax amount, payment status, vehicle data

Source: https://portal.sat.gob.gt/portal/impresion-calcomania/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.gt.sat_vehiculo import GtSatVehiculoResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SAT_VEHICULO_URL = "https://portal.sat.gob.gt/portal/impresion-calcomania/"


@register
class GtSatVehiculoSource(BaseSource):
    """Query Guatemala SAT vehicle circulation tax by plate and NIT."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="gt.sat_vehiculo",
            display_name="SAT — Impresión Calcomanía (Circulación Vehículos)",
            description="Guatemala vehicle circulation tax: payment status and vehicle data (SAT)",
            country="GT",
            url=SAT_VEHICULO_URL,
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.PLATE:
            raise SourceError(
                "gt.sat_vehiculo", f"Only plate supported, got: {input.document_type}"
            )
        placa = input.document_number.strip().upper()
        if not placa:
            raise SourceError("gt.sat_vehiculo", "License plate is required")
        nit = input.extra.get("nit", "").strip()
        if not nit:
            raise SourceError("gt.sat_vehiculo", "NIT is required (pass via extra={'nit': '...'})")
        return self._query(placa, nit, audit=input.audit)

    def _query(self, placa: str, nit: str, audit: bool = False) -> GtSatVehiculoResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("gt.sat_vehiculo", "placa", placa)

        with browser.page(SAT_VEHICULO_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill plate input
                plate_input = page.query_selector(
                    'input[id*="placa"], input[name*="placa"], '
                    'input[id*="plate"], input[name*="plate"], '
                    'input[id*="vehiculo"], input[name*="vehiculo"], '
                    'input[type="text"]'
                )
                if not plate_input:
                    raise SourceError("gt.sat_vehiculo", "Could not find plate input field")

                plate_input.fill(placa)
                logger.info("Filled plate: %s", placa)

                # Fill NIT input
                nit_input = page.query_selector(
                    'input[id*="nit"], input[name*="nit"], input[id*="NIT"], input[name*="NIT"]'
                )
                if nit_input:
                    nit_input.fill(nit)
                    logger.info("Filled NIT: %s", nit)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="consultar"], button[id*="buscar"], '
                    'button:has-text("Consultar"), button:has-text("Buscar")'
                )
                if submit:
                    submit.click()
                else:
                    plate_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, placa, nit)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("gt.sat_vehiculo", f"Query failed: {e}") from e

    def _parse_result(self, page, placa: str, nit: str) -> GtSatVehiculoResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = GtSatVehiculoResult(queried_at=datetime.now(), placa=placa, nit=nit)
        details: dict[str, str] = {}

        lower = body_text.lower()

        field_map = {
            "monto": "tax_amount",
            "total": "tax_amount",
            "impuesto": "tax_amount",
            "vehiculo": "vehicle_description",
            "vehículo": "vehicle_description",
            "descripcion": "vehicle_description",
            "descripción": "vehicle_description",
            "marca": "vehicle_description",
            "estado": "payment_status",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            lower_line = stripped.lower()
            for label, attr in field_map.items():
                if label in lower_line and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value:
                        setattr(result, attr, value)
                    break

        # Detect payment status keywords — overrides field_map for known states
        if "pagado" in lower or "al dia" in lower or "al día" in lower:
            result.payment_status = "Pagado"
        elif "pendiente" in lower or "no pagado" in lower:
            result.payment_status = "Pendiente"
        elif "vencido" in lower or "vencida" in lower:
            result.payment_status = "Vencido"
            # Collect all key:value pairs into details
            if ":" in stripped:
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip()
                if key and val:
                    details[key] = val

        result.details = details
        return result
