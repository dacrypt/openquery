"""MinSalud source — Colombian health provider/IPS/EPS habilitacion registry.

Queries the MinSalud habilitacion registry for IPS/EPS status.

Flow:
1. Navigate to habilitacion consultation page
2. Enter provider name
3. Parse result for provider type, habilitacion status

Source: https://prestadores.minsalud.gov.co/habilitacion/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.minsalud import MinsaludResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

MINSALUD_URL = "https://prestadores.minsalud.gov.co/habilitacion/"


@register
class MinsaludSource(BaseSource):
    """Query Colombian health provider habilitacion registry (MinSalud)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.minsalud",
            display_name="MinSalud — Registro de Habilitacion",
            description="Colombian health provider IPS/EPS habilitacion registry",
            country="CO",
            url=MINSALUD_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("provider_name") or input.document_number
        if not search_term:
            raise SourceError("co.minsalud", "provider_name is required")
        return self._query(search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> MinsaludResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("co.minsalud", "custom", search_term)

        with browser.page(MINSALUD_URL) as page:
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
                    raise SourceError("co.minsalud", "Could not find search input field")

                search_input.fill(search_term)

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

                result = self._parse_result(page, search_term)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("co.minsalud", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> MinsaludResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        provider_name = ""
        provider_type = ""
        habilitacion_status = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if not stripped:
                continue
            if ("nombre" in lower or "razon" in lower) and ":" in stripped:
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not provider_name:
                    provider_name = parts[1].strip()
            elif ("tipo" in lower or "naturaleza" in lower) and ":" in stripped:
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not provider_type:
                    provider_type = parts[1].strip()
            elif "habilitad" in lower and ":" in stripped:
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not habilitacion_status:
                    habilitacion_status = parts[1].strip()

        found = any(
            phrase in body_lower
            for phrase in ["habilitad", "inscrit", "activo", "prestador"]
        )

        if not habilitacion_status:
            habilitacion_status = "Habilitado" if found else "No encontrado"

        return MinsaludResult(
            queried_at=datetime.now(),
            search_term=search_term,
            provider_name=provider_name,
            provider_type=provider_type,
            habilitacion_status=habilitacion_status,
            details={"found": found},
        )
