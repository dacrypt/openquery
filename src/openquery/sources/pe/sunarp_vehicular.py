"""SUNARP Vehicular source — Peruvian vehicle registry.

Queries SUNARP for vehicle registration by license plate.
Protected by image CAPTCHA.

Flow:
1. Navigate to vehicular consultation page
2. Enter license plate number
3. Submit search
4. Parse result fields
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pe.sunarp_vehicular import SunarpVehicularResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SUNARP_URL = "https://consultavehicular.sunarp.gob.pe/"


@register
class SunarpVehicularSource(BaseSource):
    """Query Peruvian vehicle registry (SUNARP)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pe.sunarp_vehicular",
            display_name="SUNARP — Consulta Vehicular",
            description="Peruvian vehicle registry: owner, make, model, VIN, and status",
            country="PE",
            url=SUNARP_URL,
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=True,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.PLATE:
            raise SourceError(
                "pe.sunarp_vehicular",
                f"Unsupported document type: {input.document_type}. Use PLATE.",
            )
        return self._query(placa=input.document_number, audit=input.audit)

    def _query(
        self,
        placa: str = "",
        audit: bool = False,
    ) -> SunarpVehicularResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("pe.sunarp_vehicular", "placa", placa)

        with browser.page(SUNARP_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_selector(
                    "input[type='text'], #txtPlaca, input[name*='placa']",
                    timeout=15000,
                )
                page.wait_for_timeout(2000)

                plate_input = page.query_selector(
                    "#txtPlaca, input[name*='placa'], input[type='text']"
                )
                if plate_input:
                    plate_input.fill(placa)
                    logger.info("Filled placa: %s", placa)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    "#btnBuscar, input[value='Buscar'], "
                    "button:has-text('Buscar'), button:has-text('Consultar')"
                )
                if submit:
                    submit.click()
                else:
                    page.keyboard.press("Enter")

                page.wait_for_timeout(3000)
                page.wait_for_selector(
                    "table, .resultado, #divResultado, .card",
                    timeout=15000,
                )

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, placa)

                if collector:
                    result.audit = collector.generate_pdf(
                        page, result.model_dump_json()
                    )

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError(
                    "pe.sunarp_vehicular", f"Query failed: {e}"
                ) from e

    def _parse_result(self, page, placa: str) -> SunarpVehicularResult:
        """Parse the SUNARP vehicular result page."""
        from datetime import datetime

        body_text = page.inner_text("body")
        result = SunarpVehicularResult(
            queried_at=datetime.now(),
            placa=placa,
        )

        field_patterns = [
            (r"Placa[:\s]+([^\n]+)", "placa"),
            (r"Propietario[:\s]+([^\n]+)", "propietario"),
            (r"Marca[:\s]+([^\n]+)", "marca"),
            (r"Modelo[:\s]+([^\n]+)", "modelo"),
            (r"A[ñn]o[:\s]+([^\n]+)", "anio"),
            (r"Color[:\s]+([^\n]+)", "color"),
            (r"(?:VIN|Serie)[:\s]+([^\n]+)", "vin"),
            (r"Estado[:\s]+([^\n]+)", "estado"),
        ]

        for pattern, field in field_patterns:
            m = re.search(pattern, body_text, re.IGNORECASE)
            if m:
                setattr(result, field, m.group(1).strip())

        return result
