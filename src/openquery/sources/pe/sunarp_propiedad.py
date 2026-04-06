"""SUNARP Propiedad source — Peruvian property registry.

Queries the SUNARP (Superintendencia Nacional de los Registros Publicos)
for property ownership and lien data.

Flow:
1. Navigate to SUNARP consultation page
2. Enter property code
3. Parse result for owner, property type, liens

Source: https://www.sunarp.gob.pe/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pe.sunarp_propiedad import SunarpPropiedadResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SUNARP_URL = "https://www.sunarp.gob.pe/consulta-publicidad-registral.asp"


@register
class SunarpPropiedadSource(BaseSource):
    """Query Peruvian property registry (SUNARP)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pe.sunarp_propiedad",
            display_name="SUNARP — Registro de Propiedad",
            description="Peruvian property registry — ownership and liens (SUNARP)",
            country="PE",
            url=SUNARP_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_value = input.extra.get("property_code") or input.document_number
        if not search_value:
            raise SourceError("pe.sunarp_propiedad", "property_code is required")
        return self._query(search_value, audit=input.audit)

    def _query(self, search_value: str, audit: bool = False) -> SunarpPropiedadResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("pe.sunarp_propiedad", "custom", search_value)

        with browser.page(SUNARP_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[type="text"], input[id*="partida"], '
                    'input[id*="codigo"], input[id*="predio"]'
                )
                if not search_input:
                    raise SourceError("pe.sunarp_propiedad", "Could not find property code input")

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
                raise SourceError("pe.sunarp_propiedad", f"Query failed: {e}") from e

    def _parse_result(self, page, search_value: str) -> SunarpPropiedadResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        owner = ""
        property_type = ""
        liens: list[str] = []

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if not stripped:
                continue
            if ("propietario" in lower or "titular" in lower) and ":" in stripped:
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not owner:
                    owner = parts[1].strip()
            elif ("tipo" in lower or "clase" in lower) and ":" in stripped:
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not property_type:
                    property_type = parts[1].strip()
            elif "carga" in lower or "gravamen" in lower or "hipoteca" in lower:
                liens.append(stripped)

        return SunarpPropiedadResult(
            queried_at=datetime.now(),
            search_value=search_value,
            owner=owner,
            property_type=property_type,
            liens=liens,
            details={"queried": True},
        )
