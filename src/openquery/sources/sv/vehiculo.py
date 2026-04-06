"""El Salvador vehicle registry source — SERTRACEN.

Queries El Salvador's SERTRACEN public vehicle registry for
vehicle status, registration, liens, and owner info by plate or chassis.

Source: https://www.sertracen.com.sv/index.php/consultas-en-linea-del-registro-publico-de-vehiculos/consulta-de-estado-de-vehiculos
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.sv.vehiculo import SvVehiculoResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SERTRACEN_URL = (
    "https://www.sertracen.com.sv/index.php/consultas-en-linea-del-registro-publico-de-vehiculos"
    "/consulta-de-estado-de-vehiculos"
)


@register
class SvVehiculoSource(BaseSource):
    """Query El Salvador SERTRACEN vehicle registry by plate or chassis."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="sv.vehiculo",
            display_name="SERTRACEN — Registro Público de Vehículos El Salvador",
            description="El Salvador vehicle registry: status, registration, liens, owner",
            country="SV",
            url=SERTRACEN_URL,
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.PLATE:
            raise SourceError("sv.vehiculo", f"Only plate supported, got: {input.document_type}")
        search_value = input.document_number.strip().upper()
        if not search_value:
            raise SourceError("sv.vehiculo", "License plate or chassis number is required")
        return self._query(search_value, audit=input.audit)

    def _query(self, search_value: str, audit: bool = False) -> SvVehiculoResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("sv.vehiculo", "plate", search_value)

        with browser.page(SERTRACEN_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill plate/chassis input
                plate_input = page.query_selector(
                    'input[id*="placa"], input[name*="placa"], '
                    'input[id*="plate"], input[name*="plate"], '
                    'input[id*="chasis"], input[name*="chasis"], '
                    'input[id*="chassis"], input[name*="chassis"], '
                    'input[type="text"]'
                )
                if not plate_input:
                    raise SourceError("sv.vehiculo", "Could not find plate/chassis input field")

                plate_input.fill(search_value)
                logger.info("Filled search value: %s", search_value)

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

                result = self._parse_result(page, search_value)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("sv.vehiculo", f"Query failed: {e}") from e

    def _parse_result(self, page, search_value: str) -> SvVehiculoResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = SvVehiculoResult(queried_at=datetime.now(), search_value=search_value)
        details: dict[str, str] = {}
        liens: list[str] = []

        lower = body_text.lower()

        # Detect vehicle status keywords — check "inactivo" before "activo" (substring match)
        if "inactivo" in lower:
            result.vehicle_status = "Inactivo"
        elif "activo" in lower:
            result.vehicle_status = "Activo"
        elif "robado" in lower:
            result.vehicle_status = "Robado"

        # Detect liens/gravamenes
        lien_keywords = ["gravamen", "embargo", "prenda", "hipoteca"]
        for line in body_text.split("\n"):
            stripped = line.strip()
            if any(kw in stripped.lower() for kw in lien_keywords):
                liens.append(stripped)

        result.liens = liens

        field_map = {
            "propietario": "owner",
            "dueño": "owner",
            "dueno": "owner",
            "titular": "owner",
            "estado": "vehicle_status",
            "registro": "registration_status",
            "matricula": "registration_status",
            "matrícula": "registration_status",
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
