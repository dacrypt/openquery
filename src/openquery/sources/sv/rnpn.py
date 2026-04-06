"""RNPN source — El Salvador civil registry lookup.

Queries El Salvador's RNPN (Registro Nacional de las Personas Naturales)
for civil registry status by DUI number.

Source: https://www.rnpn.gob.sv/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.sv.rnpn import RnpnResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

RNPN_URL = "https://www.rnpn.gob.sv/"


@register
class RnpnSource(BaseSource):
    """Query El Salvador RNPN civil registry by DUI number."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="sv.rnpn",
            display_name="RNPN — Registro Civil",
            description=(
                "El Salvador RNPN civil registry: civil status and name by DUI number"
            ),
            country="SV",
            url=RNPN_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        dui = input.extra.get("dui", "") or input.document_number.strip()
        if not dui:
            raise SourceError("sv.rnpn", "DUI is required")
        return self._query(dui=dui, audit=input.audit)

    def _query(self, dui: str, audit: bool = False) -> RnpnResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("sv.rnpn", "dui", dui)

        with browser.page(RNPN_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "page_loaded")

                dui_input = page.query_selector(
                    'input[name*="dui"], input[name*="DUI"], '
                    'input[id*="dui"], input[id*="DUI"], '
                    'input[placeholder*="DUI"], input[placeholder*="documento"], '
                    'input[type="text"]'
                )
                if not dui_input:
                    raise SourceError("sv.rnpn", "Could not find DUI input field")

                dui_input.fill(dui)
                logger.info("Querying RNPN for DUI: %s", dui)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit_btn = page.query_selector(
                    'input[type="submit"], button[type="submit"], '
                    'button:has-text("Consultar"), button:has-text("Buscar"), '
                    'input[value*="Consultar"], input[value*="Buscar"]'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    dui_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, dui)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("sv.rnpn", f"Query failed: {e}") from e

    def _parse_result(self, page, dui: str) -> RnpnResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        nombre = ""
        civil_status = ""

        field_map = {
            "nombre": "nombre",
            "apellido": "nombre",
            "estado civil": "civil_status",
            "estado": "civil_status",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_map.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value:
                        if field == "nombre" and not nombre:
                            nombre = value
                        elif field == "civil_status" and not civil_status:
                            civil_status = value
                    break

        return RnpnResult(
            queried_at=datetime.now(),
            dui=dui,
            nombre=nombre,
            civil_status=civil_status,
            details=body_text.strip()[:500],
        )
