"""Nicaragua Registro Público source — SINARE company registry.

Queries the SINARE (Sistema Nacional de Registro) portal for company
and legal entity information.
Browser-based, public, no authentication required.

Source: https://www.registropublico.gob.ni/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ni.registro_publico import NiRegistroPublicoResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SINARE_URL = "https://www.registropublico.gob.ni/"


@register
class NiRegistroPublicoSource(BaseSource):
    """Query Nicaragua SINARE public registry by company name or NAM."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ni.registro_publico",
            display_name="Registro Público — SINARE",
            description=(
                "Nicaragua public company registry: company name, department, "
                "NAM, and status (SINARE — Registro Público)"
            ),
            country="NI",
            url=SINARE_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("company_name", "") or input.document_number
        if not search_term:
            raise SourceError("ni.registro_publico", "Company name or NAM is required")
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> NiRegistroPublicoResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("ni.registro_publico", "company_name", search_term)

        with browser.page(SINARE_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    '#txtBusqueda, input[name="txtBusqueda"], '
                    '#txtNombre, input[name="txtNombre"], '
                    'input[placeholder*="empresa"], input[placeholder*="nombre"]'
                )
                if not search_input:
                    raise SourceError(
                        "ni.registro_publico", "Could not find search input field"
                    )

                search_input.fill(search_term)
                logger.info("Filled search term: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    '#btnBuscar, input[name="btnBuscar"], '
                    '#btnConsultar, input[name="btnConsultar"], '
                    'button[type="submit"]'
                )
                if submit:
                    submit.click()
                else:
                    search_input.press("Enter")

                page.wait_for_timeout(3000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_term)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("ni.registro_publico", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> NiRegistroPublicoResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = NiRegistroPublicoResult(
            queried_at=datetime.now(), search_term=search_term
        )

        field_map = {
            "nombre": "company_name",
            "razón social": "company_name",
            "razon social": "company_name",
            "departamento": "department",
            "nam": "nam",
            "número de asiento": "nam",
            "estado": "status",
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

        result.details = {"raw": body_text.strip()[:500]}

        return result
