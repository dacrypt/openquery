"""Registro Propiedad CABA source — Buenos Aires property registry (Argentina).

Queries the CABA property registry for ownership data.

Flow:
1. Navigate to CABA property registry consultation page
2. Enter property number
3. Parse result for owner, property type

Source: https://www.buenosaires.gob.ar/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ar.registro_propiedad_caba import RegistroPropiedadCabaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

REGISTRO_CABA_URL = "https://www.buenosaires.gob.ar/registropropiedadinmueble"


@register
class RegistroPropiedadCabaSource(BaseSource):
    """Query Buenos Aires CABA property registry."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ar.registro_propiedad_caba",
            display_name="Registro de la Propiedad Inmueble CABA",
            description="Buenos Aires CABA property registry — ownership data (Argentina)",
            country="AR",
            url=REGISTRO_CABA_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_value = input.extra.get("property_number") or input.document_number
        if not search_value:
            raise SourceError("ar.registro_propiedad_caba", "property_number is required")
        return self._query(search_value, audit=input.audit)

    def _query(self, search_value: str, audit: bool = False) -> RegistroPropiedadCabaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("ar.registro_propiedad_caba", "custom", search_value)

        with browser.page(REGISTRO_CABA_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[type="text"], input[id*="partida"], '
                    'input[id*="numero"], input[id*="propiedad"]'
                )
                if not search_input:
                    raise SourceError(
                        "ar.registro_propiedad_caba", "Could not find property number input"
                    )

                search_input.fill(search_value)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="buscar"], button[id*="consultar"]'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    search_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_value)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("ar.registro_propiedad_caba", f"Query failed: {e}") from e

    def _parse_result(self, page, search_value: str) -> RegistroPropiedadCabaResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        owner = ""
        property_type = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if not stripped:
                continue
            if ("propietario" in lower or "titular" in lower or "nombre" in lower) and ":" in stripped:  # noqa: E501
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not owner:
                    owner = parts[1].strip()
            elif ("tipo" in lower or "clase" in lower or "inmueble" in lower) and ":" in stripped:
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not property_type:
                    property_type = parts[1].strip()

        return RegistroPropiedadCabaResult(
            queried_at=datetime.now(),
            search_value=search_value,
            owner=owner,
            property_type=property_type,
            details={"queried": True},
        )
