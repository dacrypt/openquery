"""SIEM source — Mexican business registry (Secretaria de Economia).

Queries SIEM for registered businesses by name, RFC, or economic activity.

Flow:
1. Navigate to SIEM search portal
2. Enter search criteria (nombre, RFC, or actividad)
3. Submit and parse business list
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.mx.siem import EmpresaSiem, SiemResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SIEM_URL = "https://siem.economia.gob.mx/"


@register
class SiemSource(BaseSource):
    """Query Mexican SIEM business registry."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="mx.siem",
            display_name="SIEM — Directorio Empresarial",
            description="Mexican business registry: company info, RFC, address, and economic activity",
            country="MX",
            url=SIEM_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        nombre = input.extra.get("nombre", "")
        rfc = input.extra.get("rfc", "")
        actividad = input.extra.get("actividad", "")
        consulta = nombre or rfc or actividad or input.document_number
        if not consulta:
            raise SourceError(
                "mx.siem",
                "nombre, rfc, or actividad is required (pass via extra.nombre, extra.rfc, or extra.actividad)",
            )
        return self._query(consulta, audit=input.audit)

    def _query(self, consulta: str, audit: bool = False) -> SiemResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("mx.siem", "consulta", consulta)

        with browser.page(SIEM_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill search field
                search_input = page.query_selector(
                    'input[name*="nombre"], input[name*="busca"], input[name*="razon"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("mx.siem", "Could not find search input field")
                search_input.fill(consulta)
                logger.info("Filled search: %s", consulta)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    "button:has-text('Buscar'), button:has-text('Consultar')"
                )
                if submit:
                    submit.click()
                else:
                    search_input.press("Enter")

                page.wait_for_timeout(3000)
                page.wait_for_selector("body", timeout=15000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, consulta)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("mx.siem", f"Query failed: {e}") from e

    def _parse_result(self, page, consulta: str) -> SiemResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        result = SiemResult(queried_at=datetime.now(), consulta=consulta)

        # Parse result table rows
        rows = page.query_selector_all("table tr, .empresas tr, .resultado tr")

        empresas: list[EmpresaSiem] = []
        for row in rows[1:]:  # skip header
            cells = row.query_selector_all("td")
            if len(cells) >= 4:
                values = [(c.inner_text() or "").strip() for c in cells]
                empresa = EmpresaSiem(
                    nombre=values[0] if len(values) > 0 else "",
                    rfc=values[1] if len(values) > 1 else "",
                    direccion=values[2] if len(values) > 2 else "",
                    municipio=values[3] if len(values) > 3 else "",
                    estado=values[4] if len(values) > 4 else "",
                    actividad=values[5] if len(values) > 5 else "",
                    tamano=values[6] if len(values) > 6 else "",
                    telefono=values[7] if len(values) > 7 else "",
                )
                empresas.append(empresa)

        result.empresas = empresas
        result.total_empresas = len(empresas)

        # Try to extract total from page text
        m = re.search(r"(\d+)\s*(?:empresa|resultado|registro)", body_text, re.IGNORECASE)
        if m:
            result.total_empresas = max(result.total_empresas, int(m.group(1)))

        return result
