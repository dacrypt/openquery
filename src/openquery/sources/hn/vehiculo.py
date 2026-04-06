"""Honduras vehicle registry source — IP license plate lookup.

Queries Honduras' Instituto de la Propiedad (IP) vehicle registry
for matricula fee and registration status by license plate.

Source: https://placas.ip.gob.hn/vehiculos
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.hn.vehiculo import HnVehiculoResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

VEHICULO_URL = "https://placas.ip.gob.hn/vehiculos"


@register
class HnVehiculoSource(BaseSource):
    """Query Honduras IP vehicle registry by license plate."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="hn.vehiculo",
            display_name="IP — Registro de Vehículos Honduras",
            description="Honduras vehicle registry: matricula fee, registration status (IP)",
            country="HN",
            url=VEHICULO_URL,
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.PLATE:
            raise SourceError("hn.vehiculo", f"Only plate supported, got: {input.document_type}")
        placa = input.document_number.strip().upper()
        if not placa:
            raise SourceError("hn.vehiculo", "License plate is required")
        return self._query(placa, audit=input.audit)

    def _query(self, placa: str, audit: bool = False) -> HnVehiculoResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("hn.vehiculo", "placa", placa)

        with browser.page(VEHICULO_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill plate input
                placa_input = page.query_selector(
                    'input[id*="placa"], input[name*="placa"], '
                    'input[id*="plate"], input[name*="plate"], '
                    'input[type="text"]'
                )
                if not placa_input:
                    raise SourceError("hn.vehiculo", "Could not find plate input field")

                placa_input.fill(placa)
                logger.info("Filled placa: %s", placa)

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
                    placa_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, placa)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("hn.vehiculo", f"Query failed: {e}") from e

    def _parse_result(self, page, placa: str) -> HnVehiculoResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = HnVehiculoResult(queried_at=datetime.now(), placa=placa)
        details: dict[str, str] = {}

        lower = body_text.lower()

        # Detect registration status keywords
        if "al día" in lower or "al dia" in lower:
            result.registration_status = "Al día"
        elif "moroso" in lower or "deuda" in lower:
            result.registration_status = "Moroso"
        elif "solvente" in lower:
            result.registration_status = "Solvente"

        field_map = {
            "matrícula": "matricula_fee",
            "matricula": "matricula_fee",
            "monto": "matricula_fee",
            "descripción": "vehicle_description",
            "descripcion": "vehicle_description",
            "vehículo": "vehicle_description",
            "vehiculo": "vehicle_description",
            "modelo": "vehicle_description",
            "estado": "registration_status",
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
            # Collect all key:value pairs into details
            if ":" in stripped:
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip()
                if key and val:
                    details[key] = val

        result.details = details
        return result
