"""SRI Vehiculos source — Ecuador vehicle tax and registration.

Queries Ecuador's SRI (Servicio de Rentas Internas) for vehicle tax data
and SPPAT (Sistema Publico para Pago del Accidente de Transito) by plate.

Flow:
1. Navigate to the SRI vehicle tax consultation page
2. Enter plate number
3. Submit and parse result (impuesto vehicular, SPPAT, total)

Source: https://www.sri.gob.ec/impuestos-vehiculares
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ec.sri_vehiculos import SriVehiculosResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SRI_VEHICULOS_URL = "https://www.sri.gob.ec/impuestos-vehiculares"


@register
class SriVehiculosSource(BaseSource):
    """Query Ecuador vehicle tax and registration data from SRI."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ec.sri_vehiculos",
            display_name="SRI — Impuestos Vehiculares",
            description="Ecuador vehicle tax (impuesto vehicular) and SPPAT lookup by plate",
            country="EC",
            url=SRI_VEHICULOS_URL,
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.PLATE:
            raise SourceError(
                "ec.sri_vehiculos", f"Only plate supported, got: {input.document_type}"
            )

        placa = input.document_number.strip().upper()
        if not placa:
            raise SourceError("ec.sri_vehiculos", "Plate number is required")

        return self._query(placa, audit=input.audit)

    def _query(self, placa: str, audit: bool = False) -> SriVehiculosResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("ec.sri_vehiculos", "plate", placa)

        with browser.page(SRI_VEHICULOS_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill plate input
                plate_input = page.query_selector(
                    'input[id*="placa"], input[name*="placa"], '
                    'input[id*="plate"], input[name*="plate"], '
                    'input[placeholder*="placa"], input[placeholder*="Placa"], '
                    'input[type="text"]'
                )
                if not plate_input:
                    raise SourceError("ec.sri_vehiculos", "Could not find plate input field")

                plate_input.fill(placa)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="consultar"], button[id*="buscar"], '
                    'button:has-text("Consultar"), button:has-text("Buscar")'
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
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("ec.sri_vehiculos", f"Query failed: {e}") from e

    def _parse_result(self, page, placa: str) -> SriVehiculosResult:
        body_text = page.inner_text("body")

        vehicle_description = ""
        brand = ""
        model = ""
        year = ""
        impuesto_vehicular = ""
        sppat_amount = ""
        total_due = ""
        registration_status = ""
        details: dict[str, str] = {}

        for line in body_text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            lower = stripped.lower()

            if ":" in stripped:
                key, _, val = stripped.partition(":")
                key_s = key.strip()
                val_s = val.strip()

                if not key_s or not val_s:
                    continue

                details[key_s] = val_s

                if any(k in lower for k in ("marca", "brand")):
                    brand = val_s
                elif any(k in lower for k in ("modelo", "model")):
                    model = val_s
                elif any(k in lower for k in ("año", "anio", "year", "modelo año")):
                    year = val_s
                elif any(
                    k in lower for k in ("descripcion", "descripción", "vehiculo", "vehículo")
                ):
                    vehicle_description = val_s
                elif "sppat" in lower:
                    sppat_amount = val_s
                elif any(k in lower for k in ("impuesto vehicular", "impuesto a los vehiculos")):
                    impuesto_vehicular = val_s
                elif any(k in lower for k in ("total", "valor total", "monto total")):
                    total_due = val_s
                elif any(k in lower for k in ("estado", "status")):
                    registration_status = val_s

        # Try table-based parsing as fallback
        rows = page.query_selector_all("table tr, .result-row, .data-row")
        for row in rows:
            cells = row.query_selector_all("td, th")
            if len(cells) >= 2:
                label = cells[0].inner_text().strip()
                value = cells[1].inner_text().strip()
                if label and value:
                    details[label] = value
                    lower_label = label.lower()
                    if any(k in lower_label for k in ("marca", "brand")) and not brand:
                        brand = value
                    elif any(k in lower_label for k in ("modelo", "model")) and not model:
                        model = value
                    elif any(k in lower_label for k in ("año", "anio", "year")) and not year:
                        year = value
                    elif (
                        any(k in lower_label for k in ("descripcion", "descripción"))
                        and not vehicle_description
                    ):
                        vehicle_description = value
                    elif "sppat" in lower_label and not sppat_amount:
                        sppat_amount = value
                    elif (
                        any(k in lower_label for k in ("impuesto vehicular",))
                        and not impuesto_vehicular
                    ):
                        impuesto_vehicular = value
                    elif any(k in lower_label for k in ("total",)) and not total_due:
                        total_due = value
                    elif any(k in lower_label for k in ("estado",)) and not registration_status:
                        registration_status = value

        return SriVehiculosResult(
            placa=placa,
            vehicle_description=vehicle_description,
            brand=brand,
            model=model,
            year=year,
            impuesto_vehicular=impuesto_vehicular,
            sppat_amount=sppat_amount,
            total_due=total_due,
            registration_status=registration_status,
            details=details,
        )
