"""Superir source — Chilean insolvency and bankruptcy registry.

Queries the Superintendencia de Insolvencia y Reemprendimiento (Superir)
for bankruptcy and insolvency proceedings by RUT.

Flow:
1. Navigate to Superir search
2. Enter RUT
3. Parse results

Source: https://www.superir.gob.cl/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.cl.superir import BankruptcyProceeding, SuperirResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SUPERIR_URL = "https://www.superir.gob.cl/consulta-de-procedimientos/"


@register
class SuperirSource(BaseSource):
    """Query Chilean insolvency/bankruptcy registry (Superir)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="cl.superir",
            display_name="Superir — Insolvencia y Reemprendimiento",
            description="Chilean insolvency and bankruptcy proceedings (Superintendencia de Insolvencia)",
            country="CL",
            url=SUPERIR_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        rut = input.extra.get("rut", "") or input.document_number
        if not rut:
            raise SourceError("cl.superir", "RUT is required (pass via extra.rut)")
        return self._query(rut, audit=input.audit)

    def _query(self, rut: str, audit: bool = False) -> SuperirResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("cl.superir", "rut", rut)

        with browser.page(SUPERIR_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(2000)

                # Find and fill RUT input
                rut_input = page.query_selector(
                    'input[type="text"][id*="rut"], '
                    'input[type="text"][name*="rut"], '
                    'input[type="text"][placeholder*="RUT"], '
                    'input[type="text"]'
                )
                if not rut_input:
                    raise SourceError("cl.superir", "Could not find RUT input field")

                rut_input.fill(rut)
                logger.info("Searching Superir for RUT: %s", rut)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit search
                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button:has-text("Buscar"), button:has-text("Consultar")'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    rut_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, rut)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("cl.superir", f"Query failed: {e}") from e

    def _parse_result(self, page, rut: str) -> SuperirResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        result = SuperirResult(
            queried_at=datetime.now(),
            rut=rut,
        )

        # Try to extract from result tables
        rows = page.query_selector_all("table tr, .resultado, .item-resultado")

        procedimientos = []
        for row in rows:
            text = row.inner_text()
            if not text.strip():
                continue
            cells = text.split("\t")
            if len(cells) >= 2:
                procedimientos.append(BankruptcyProceeding(
                    tipo_procedimiento=cells[0].strip() if cells else "",
                    estado=cells[1].strip() if len(cells) > 1 else "",
                    tribunal=cells[2].strip() if len(cells) > 2 else "",
                    fecha_resolucion=cells[3].strip() if len(cells) > 3 else "",
                    veedor_liquidador=cells[4].strip() if len(cells) > 4 else "",
                ))

        result.procedimientos = procedimientos
        result.total_procedimientos = len(procedimientos)
        result.tiene_procedimiento = len(procedimientos) > 0

        # Extract name from page
        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if "nombre" in lower and ":" in stripped:
                result.nombre = stripped.split(":", 1)[1].strip()
                break

        return result
