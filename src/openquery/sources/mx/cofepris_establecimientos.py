"""COFEPRIS Establecimientos source — Mexican health establishments registry.

Queries COFEPRIS for health establishment permits.

Flow:
1. Navigate to COFEPRIS consultation page
2. Enter establishment name
3. Parse result for permit status

Source: https://www.gob.mx/cofepris
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.mx.cofepris_establecimientos import CofeprisEstablecimientosResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

COFEPRIS_URL = "https://www.gob.mx/cofepris/acciones-y-programas/establecimientos"


@register
class CofeprisEstablecimientosSource(BaseSource):
    """Query Mexican health establishments registry (COFEPRIS)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="mx.cofepris_establecimientos",
            display_name="COFEPRIS — Establecimientos de Salud",
            description="Mexican health establishments and permits registry (COFEPRIS)",
            country="MX",
            url=COFEPRIS_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("establishment_name") or input.document_number
        if not search_term:
            raise SourceError("mx.cofepris_establecimientos", "establishment_name is required")
        return self._query(search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> CofeprisEstablecimientosResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("mx.cofepris_establecimientos", "custom", search_term)

        with browser.page(COFEPRIS_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[type="text"], input[type="search"], '
                    'input[id*="buscar"], input[id*="nombre"]'
                )
                if not search_input:
                    raise SourceError(
                        "mx.cofepris_establecimientos", "Could not find search input field"
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
                raise SourceError(
                    "mx.cofepris_establecimientos", f"Query failed: {e}"
                ) from e

    def _parse_result(self, page, search_term: str) -> CofeprisEstablecimientosResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        establishment_name = ""
        permit_status = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if not stripped:
                continue
            if ("nombre" in lower or "establecimiento" in lower) and ":" in stripped:
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not establishment_name:
                    establishment_name = parts[1].strip()
            elif ("estado" in lower or "permiso" in lower or "licencia" in lower) and ":" in stripped:  # noqa: E501
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not permit_status:
                    permit_status = parts[1].strip()

        found = any(
            phrase in body_lower
            for phrase in ["autorizado", "activo", "vigente", "permiso"]
        )

        if not permit_status:
            permit_status = "Autorizado" if found else "No encontrado"

        return CofeprisEstablecimientosResult(
            queried_at=datetime.now(),
            search_term=search_term,
            establishment_name=establishment_name,
            permit_status=permit_status,
            details={"found": found},
        )
