"""INTT source — Venezuela vehicle registration.

Queries the INTT (Instituto Nacional de Transporte Terrestre) public
consultation portal for vehicle registration information by license plate.

Flow:
1. Navigate to INTT public consultation page
2. Enter license plate number
3. Submit and parse vehicle data, registration status, owner

Source: https://www.intt.gob.ve/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ve.intt import InttResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

INTT_URL = "https://www.intt.gob.ve/"


@register
class InttSource(BaseSource):
    """Query Venezuela vehicle registration by license plate (INTT)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ve.intt",
            display_name="INTT — Consulta de Vehículos",
            description="Venezuela vehicle registration: vehicle data, registration status, owner",
            country="VE",
            url=INTT_URL,
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.PLATE:
            raise SourceError(
                "ve.intt",
                f"Unsupported document type: {input.document_type}. Use plate.",
            )
        placa = input.document_number.strip().upper()
        if not placa:
            raise SourceError("ve.intt", "placa is required")
        return self._query(placa, audit=input.audit)

    def _query(self, placa: str, audit: bool = False) -> InttResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("ve.intt", "placa", placa)

        with browser.page(INTT_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(2000)

                # Find plate input field
                placa_input = page.query_selector(
                    'input[name*="placa"], input[name*="plate"], '
                    'input[id*="placa"], input[id*="plate"], '
                    'input[placeholder*="placa"], input[placeholder*="Placa"], '
                    'input[type="text"]'
                )
                if not placa_input:
                    raise SourceError("ve.intt", "Could not find plate input field")

                placa_input.fill(placa)
                logger.info("Querying INTT for plate: %s", placa)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit form
                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="consultar"], button[id*="buscar"], '
                    'a[id*="consultar"]'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    placa_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, placa)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("ve.intt", f"Query failed: {e}") from e

    def _parse_result(self, page, placa: str) -> InttResult:
        """Parse INTT result page for vehicle registration info."""
        from datetime import datetime

        body_text = page.inner_text("body")

        vehicle_description = ""
        registration_status = ""
        owner = ""
        details: dict[str, str] = {}

        for line in body_text.split("\n"):
            stripped = line.strip()
            if not stripped or ":" not in stripped:
                continue
            key, _, val = stripped.partition(":")
            key_lower = key.strip().lower()
            val_clean = val.strip()
            if not val_clean:
                continue

            details[key.strip()] = val_clean

            if any(k in key_lower for k in ["marca", "modelo", "vehiculo", "descripcion", "tipo"]):
                if not vehicle_description:
                    vehicle_description = val_clean
            elif any(k in key_lower for k in ["estado", "estatus", "situacion", "status"]):
                if not registration_status:
                    registration_status = val_clean
            elif any(k in key_lower for k in ["propietario", "titular", "nombre", "dueno"]):
                if not owner:
                    owner = val_clean

        # Fallback: try table rows
        if not vehicle_description:
            rows = page.query_selector_all("table tr, .result-row, .item")
            for row in rows:
                text = row.inner_text().strip()
                text_lower = text.lower()
                if (
                    any(k in text_lower for k in ["marca", "modelo", "vehiculo"])
                    and ":" in text
                    and not vehicle_description
                ):
                    vehicle_description = text.split(":", 1)[1].strip()
                elif (
                    any(k in text_lower for k in ["estado", "estatus"])
                    and ":" in text
                    and not registration_status
                ):
                    registration_status = text.split(":", 1)[1].strip()
                elif (
                    any(k in text_lower for k in ["propietario", "titular"])
                    and ":" in text
                    and not owner
                ):
                    owner = text.split(":", 1)[1].strip()

        return InttResult(
            queried_at=datetime.now(),
            placa=placa,
            vehicle_description=vehicle_description,
            registration_status=registration_status,
            owner=owner,
            details=details,
        )
