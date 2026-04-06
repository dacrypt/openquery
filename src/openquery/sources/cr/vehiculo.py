"""Costa Rica vehicle registry source — plate lookup.

Queries Hacienda's TICA vehicle registry for ownership and vehicle data.
Browser-based, no CAPTCHA required.

Source: https://ticaconsultas.hacienda.go.cr/Tica/hrgvehiculos.aspx
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.cr.vehiculo import CrVehiculoResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

VEHICULO_URL = "https://ticaconsultas.hacienda.go.cr/Tica/hrgvehiculos.aspx"


@register
class CrVehiculoSource(BaseSource):
    """Query Costa Rica Hacienda TICA vehicle registry by plate."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="cr.vehiculo",
            display_name="Hacienda TICA — Registro de Vehículos",
            description=(
                "Costa Rica vehicle registry: owner, brand, model, year, engine, "
                "use type (Ministerio de Hacienda TICA)"
            ),
            country="CR",
            url=VEHICULO_URL,
            supported_inputs=[DocumentType.PLATE, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        placa = input.extra.get("placa", "") or input.document_number
        if not placa:
            raise SourceError("cr.vehiculo", "Placa is required")
        return self._query(placa.strip().upper(), audit=input.audit)

    def _query(self, placa: str, audit: bool = False) -> CrVehiculoResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("cr.vehiculo", "placa", placa)

        with browser.page(VEHICULO_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                placa_input = page.query_selector(
                    '#txtPlaca, input[name="txtPlaca"], #txtplaca, input[name="txtplaca"]'
                )
                if not placa_input:
                    raise SourceError("cr.vehiculo", "Could not find plate input field")

                placa_input.fill(placa)
                logger.info("Filled placa: %s", placa)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    '#btnConsultar, input[name="btnConsultar"], #btnBuscar, input[name="btnBuscar"]'
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
                raise SourceError("cr.vehiculo", f"Query failed: {e}") from e

    def _parse_result(self, page, placa: str) -> CrVehiculoResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        result = CrVehiculoResult(
            queried_at=datetime.now(),
            placa=placa,
        )

        field_patterns = {
            "propietario": "owner",
            "dueño": "owner",
            "nombre": "owner",
            "marca": "brand",
            "modelo": "model",
            "año": "year",
            "año del vehículo": "year",
            "motor": "engine",
            "número de motor": "engine",
            "uso": "use_type",
            "tipo de uso": "use_type",
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
