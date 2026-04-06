"""DINARDAP source — Ecuador identity and property lookup.

Queries Ecuador's DINARDAP (Dirección Nacional de Registro de Datos Públicos)
for identity data and property ownership records by cedula or property number.

Flow:
1. Navigate to the DINARDAP consultation page
2. Enter cedula or property number
3. Submit and parse result

Source: https://www.dinardap.gob.ec/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ec.dinardap import DinardapResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

DINARDAP_URL = "https://www.dinardap.gob.ec/"


@register
class DinardapSource(BaseSource):
    """Query Ecuador identity and property data from DINARDAP."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ec.dinardap",
            display_name="DINARDAP — Registro de Datos Públicos",
            description="Ecuador identity and property lookup from DINARDAP",
            country="EC",
            url=DINARDAP_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CEDULA:
            raise SourceError("ec.dinardap", f"Only cedula supported, got: {input.document_type}")

        cedula = input.document_number.strip()
        if not cedula:
            raise SourceError("ec.dinardap", "Cedula number is required")

        return self._query(cedula, audit=input.audit)

    def _query(self, cedula: str, audit: bool = False) -> DinardapResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("ec.dinardap", "cedula", cedula)

        with browser.page(DINARDAP_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill cedula input
                cedula_input = page.query_selector(
                    'input[id*="cedula"], input[name*="cedula"], '
                    'input[id*="numero"], input[name*="numero"], '
                    'input[type="text"]'
                )
                if not cedula_input:
                    raise SourceError("ec.dinardap", "Could not find cedula input field")

                cedula_input.fill(cedula)

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
                    cedula_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, cedula)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("ec.dinardap", f"Query failed: {e}") from e

    def _parse_result(self, page, cedula: str) -> DinardapResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        nombre = ""
        property_records: list[str] = []
        details: dict[str, str] = {}

        for line in body_text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            lower = stripped.lower()
            if ("nombre" in lower or "apellido" in lower) and ":" in stripped:
                nombre = stripped.split(":", 1)[1].strip()
            elif (
                "predio" in lower or "propiedad" in lower or "inmueble" in lower
            ) and ":" in stripped:
                val = stripped.split(":", 1)[1].strip()
                if val:
                    property_records.append(val)
            elif ":" in stripped:
                key, _, val = stripped.partition(":")
                if key.strip() and val.strip():
                    details[key.strip()] = val.strip()

        return DinardapResult(
            queried_at=datetime.now(),
            cedula=cedula,
            nombre=nombre,
            property_records=property_records,
            details=details,
        )
