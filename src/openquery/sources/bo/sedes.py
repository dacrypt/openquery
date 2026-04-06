"""SEDES source — Bolivian health establishments registry.

Queries SEDES (Servicio Departamental de Salud) for health establishment permits.

Flow:
1. Navigate to SEDES/MinSalud consultation page
2. Enter establishment name
3. Parse result for permit status, department

Source: https://www.minsalud.gob.bo/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.bo.sedes import SedesResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SEDES_URL = "https://www.minsalud.gob.bo/servicios/establecimientos-de-salud"


@register
class SedesSource(BaseSource):
    """Query Bolivian health establishments registry (SEDES)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="bo.sedes",
            display_name="SEDES Bolivia — Establecimientos de Salud",
            description="Bolivian health establishments registry (SEDES/MinSalud)",
            country="BO",
            url=SEDES_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("establishment_name") or input.document_number
        if not search_term:
            raise SourceError("bo.sedes", "establishment_name is required")
        return self._query(search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> SedesResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("bo.sedes", "custom", search_term)

        with browser.page(SEDES_URL) as page:
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
                    raise SourceError("bo.sedes", "Could not find search input field")

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
                raise SourceError("bo.sedes", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> SedesResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        establishment_name = ""
        permit_status = ""
        department = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if not stripped:
                continue
            if ("nombre" in lower or "establecimiento" in lower) and ":" in stripped:
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not establishment_name:
                    establishment_name = parts[1].strip()
            elif ("estado" in lower or "permiso" in lower) and ":" in stripped:
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not permit_status:
                    permit_status = parts[1].strip()
            elif "departamento" in lower and ":" in stripped:
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not department:
                    department = parts[1].strip()

        found = any(
            phrase in body_lower
            for phrase in ["autorizado", "activo", "habilitado", "permiso"]
        )

        if not permit_status:
            permit_status = "Autorizado" if found else "No encontrado"

        return SedesResult(
            queried_at=datetime.now(),
            search_term=search_term,
            establishment_name=establishment_name,
            permit_status=permit_status,
            department=department,
            details={"found": found},
        )
