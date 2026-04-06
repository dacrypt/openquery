"""Retención de Vehículos source — Colombian impounded vehicles lookup.

Queries transit authority portals for vehicle retention/impound status
by license plate number.

Flow:
1. Navigate to transit authority consultation page
2. Enter vehicle plate number
3. Submit and parse retention status

Source: https://portal.barranquilla.gov.co:8181/mov_estadoVehiculo/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.retencion_vehiculos import RetencionVehiculosResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

RETENCION_URL = "https://portal.barranquilla.gov.co:8181/mov_estadoVehiculo/"


@register
class RetencionVehiculosSource(BaseSource):
    """Query Colombian impounded/retained vehicles by plate."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.retencion_vehiculos",
            display_name="Tránsito — Retención de Vehículos",
            description="Colombian impounded/retained vehicles lookup",
            country="CO",
            url=RETENCION_URL,
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.PLATE:
            raise SourceError(
                "co.retencion_vehiculos",
                f"Only PLATE document type supported, got: {input.document_type}",
            )
        return self._query(input.document_number, audit=input.audit)

    def _query(self, placa: str, audit: bool = False) -> RetencionVehiculosResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("co.retencion_vehiculos", "plate", placa)

        with browser.page(RETENCION_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill plate number — Angular Material input
                plate_input = page.query_selector(
                    'input[placeholder*="ABC123"], input.mat-mdc-input-element, input[type="text"]'
                )
                if not plate_input:
                    raise SourceError("co.retencion_vehiculos", "Could not find plate input field")

                plate_input.fill(placa.upper())
                logger.info("Searching retención for plate: %s", placa)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit — Angular button
                submit_btn = page.query_selector(
                    'button.btn-primary, button[type="submit"], input[type="submit"]'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    plate_input.press("Enter")

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
                raise SourceError("co.retencion_vehiculos", f"Query failed: {e}") from e

    def _parse_result(self, page, placa: str) -> RetencionVehiculosResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        result = RetencionVehiculosResult(
            queried_at=datetime.now(),
            placa=placa.upper(),
        )

        # Detect retention status
        no_retention = any(
            phrase in body_lower
            for phrase in [
                "no registra",
                "no se encontr",
                "sin retención",
                "sin retencion",
                "no tiene retención",
            ]
        )

        has_retention = (
            any(
                phrase in body_lower
                for phrase in [
                    "retenido",
                    "retención",
                    "retencion",
                    "inmovilizado",
                ]
            )
            and not no_retention
        )

        result.esta_retenido = has_retention

        # Try to extract details from text lines
        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if ("patio" in lower or "parqueadero" in lower) and ":" in stripped:
                result.patio = stripped.split(":", 1)[1].strip()
            elif (
                "fecha" in lower
                and ("retención" in lower or "retencion" in lower or "inmoviliz" in lower)
            ) and ":" in stripped:
                result.fecha_retencion = stripped.split(":", 1)[1].strip()
            elif "autoridad" in lower and ":" in stripped:
                result.autoridad = stripped.split(":", 1)[1].strip()
            elif (
                "motivo" in lower or "causal" in lower or "razón" in lower or "razon" in lower
            ) and ":" in stripped:
                result.motivo = stripped.split(":", 1)[1].strip()
            elif "estado" in lower and ":" in stripped and not result.estado:
                result.estado = stripped.split(":", 1)[1].strip()

        # Try to extract from table if present
        if not result.patio:
            table_rows = page.query_selector_all("table tr")
            for row in table_rows:
                cells = row.query_selector_all("td")
                if len(cells) >= 2:
                    cell_texts = [c.inner_text().strip() for c in cells]
                    header = cell_texts[0].lower()
                    value = cell_texts[1]
                    if "patio" in header or "parqueadero" in header:
                        result.patio = value
                    elif "fecha" in header:
                        result.fecha_retencion = value
                    elif "motivo" in header or "causal" in header:
                        result.motivo = value
                    elif "autoridad" in header:
                        result.autoridad = value
                    elif "estado" in header:
                        result.estado = value

        if has_retention:
            result.mensaje = f"Vehículo {placa.upper()} se encuentra retenido"
        else:
            result.mensaje = f"Vehículo {placa.upper()} no registra retención"

        return result
