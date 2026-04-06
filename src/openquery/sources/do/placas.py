"""Dominican Republic DGII placas source — vehicle plate lookup.

Queries DGII for vehicle plate owner, status, and registration data.

Source: https://dgii.gov.do/vehiculosMotor/consultas/Paginas/consultaPlacas.aspx
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.do.placas import DoPlacasResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

PLACAS_URL = "https://dgii.gov.do/vehiculosMotor/consultas/Paginas/consultaPlacas.aspx"


@register
class DoPlacasSource(BaseSource):
    """Query Dominican Republic DGII vehicle plate registry."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="do.placas",
            display_name="DGII — Consulta Placas",
            description="Dominican Republic vehicle plate: owner, status, registration data (DGII)",
            country="DO",
            url=PLACAS_URL,
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        placa = input.document_number or input.extra.get("placa", "")
        if not placa:
            raise SourceError("do.placas", "Plate number is required")
        return self._query(placa.strip().upper(), audit=input.audit)

    def _query(self, placa: str, audit: bool = False) -> DoPlacasResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("do.placas", "plate", placa)

        with browser.page(PLACAS_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                placa_input = page.query_selector(
                    'input[id*="Placa"], input[name*="Placa"], '
                    'input[id*="placa"], input[name*="placa"], '
                    'input[type="text"]'
                )
                if not placa_input:
                    raise SourceError("do.placas", "Could not find plate input field")

                placa_input.fill(placa)
                logger.info("Filled placa: %s", placa)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'input[id*="btnBuscar"], input[id*="btnConsultar"], '
                    'button[type="submit"], input[type="submit"]'
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
                raise SourceError("do.placas", f"Query failed: {e}") from e

    def _parse_result(self, page, placa: str) -> DoPlacasResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = DoPlacasResult(queried_at=datetime.now(), placa=placa)

        field_map = {
            "propietario": "owner",
            "nombre": "owner",
            "estado": "plate_status",
            "descripcion": "vehicle_description",
            "marca": "vehicle_description",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_map.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value:
                        setattr(result, field, value)
                    break

        if body_text.strip():
            result.details = body_text.strip()[:500]

        return result
