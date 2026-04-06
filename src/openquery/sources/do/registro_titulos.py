"""Registro Titulos source — Dominican Republic land titles registry.

Queries the Registro de Titulos of the Dominican Republic for land title status.

Flow:
1. Navigate to Registro de Titulos consultation page
2. Enter parcel number
3. Parse result for title status, owner

Source: https://ri.gob.do/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.do.registro_titulos import RegistroTitulosResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

REGISTRO_DO_URL = "https://ri.gob.do/consulta"


@register
class RegistroTitulosSource(BaseSource):
    """Query Dominican Republic land titles registry."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="do.registro_titulos",
            display_name="Registro de Titulos — Republica Dominicana",
            description="Dominican Republic land titles registry",
            country="DO",
            url=REGISTRO_DO_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_value = input.extra.get("parcel_number") or input.document_number
        if not search_value:
            raise SourceError("do.registro_titulos", "parcel_number is required")
        return self._query(search_value, audit=input.audit)

    def _query(self, search_value: str, audit: bool = False) -> RegistroTitulosResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("do.registro_titulos", "custom", search_value)

        with browser.page(REGISTRO_DO_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[type="text"], input[id*="parcela"], '
                    'input[id*="matricula"], input[id*="numero"]'
                )
                if not search_input:
                    raise SourceError("do.registro_titulos", "Could not find parcel number input")

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
                raise SourceError("do.registro_titulos", f"Query failed: {e}") from e

    def _parse_result(self, page, search_value: str) -> RegistroTitulosResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        title_status = ""
        owner = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if not stripped:
                continue
            if ("propietario" in lower or "titular" in lower or "nombre" in lower) and ":" in stripped:  # noqa: E501
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not owner:
                    owner = parts[1].strip()
            elif ("estado" in lower or "titulo" in lower) and ":" in stripped:
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not title_status:
                    title_status = parts[1].strip()

        found = any(
            phrase in body_lower
            for phrase in ["titulo", "registrado", "vigente", "activo"]
        )

        if not title_status:
            title_status = "Registrado" if found else "No encontrado"

        return RegistroTitulosResult(
            queried_at=datetime.now(),
            search_value=search_value,
            title_status=title_status,
            owner=owner,
            details={"queried": True},
        )
