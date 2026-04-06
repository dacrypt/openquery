"""MINSA Establecimientos source — Panamanian health providers registry.

Queries MINSA (Ministerio de Salud de Panama) for health provider licenses.

Flow:
1. Navigate to MINSA consultation page
2. Enter provider name
3. Parse result for license status

Source: https://www.minsa.gob.pa/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pa.minsa_establecimientos import MinsaEstablecimientosResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

MINSA_PA_URL = "https://www.minsa.gob.pa/informacion-salud/establecimientos-de-salud"


@register
class MinsaEstablecimientosSource(BaseSource):
    """Query Panamanian health providers registry (MINSA)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pa.minsa_establecimientos",
            display_name="MINSA Panama — Establecimientos de Salud",
            description="Panamanian health providers and licenses registry (MINSA)",
            country="PA",
            url=MINSA_PA_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("provider_name") or input.document_number
        if not search_term:
            raise SourceError("pa.minsa_establecimientos", "provider_name is required")
        return self._query(search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> MinsaEstablecimientosResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("pa.minsa_establecimientos", "custom", search_term)

        with browser.page(MINSA_PA_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[type="text"], input[type="search"], '
                    'input[id*="nombre"], input[id*="buscar"]'
                )
                if not search_input:
                    raise SourceError(
                        "pa.minsa_establecimientos", "Could not find search input field"
                    )

                search_input.fill(search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="buscar"]'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    search_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_term)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("pa.minsa_establecimientos", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> MinsaEstablecimientosResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        provider_name = ""
        license_status = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if not stripped:
                continue
            if ("nombre" in lower or "proveedor" in lower) and ":" in stripped:
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not provider_name:
                    provider_name = parts[1].strip()
            elif ("licencia" in lower or "estado" in lower) and ":" in stripped:
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not license_status:
                    license_status = parts[1].strip()

        found = any(
            phrase in body_lower
            for phrase in ["licencia", "autorizado", "activo", "habilitado"]
        )

        if not license_status:
            license_status = "Licenciado" if found else "No encontrado"

        return MinsaEstablecimientosResult(
            queried_at=datetime.now(),
            search_term=search_term,
            provider_name=provider_name,
            license_status=license_status,
            details={"found": found},
        )
