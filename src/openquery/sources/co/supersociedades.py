"""Supersociedades source — Colombian insolvency proceedings.

Queries Supersociedades for insolvency proceedings (Ley 1116)
by NIT, cedula, or business name.

Flow:
1. Navigate to Supersociedades insolvency search
2. Enter search term
3. Parse results

Source: https://www.supersociedades.gov.co/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.supersociedades import InsolvencyProceeding, SupersociedadesResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SUPERSOCIEDADES_URL = "https://www.supersociedades.gov.co/delegatura-procedimientos-de-insolvencia/consulta-de-procesos"


@register
class SupersociedadesSource(BaseSource):
    """Query Colombian insolvency proceedings (Supersociedades / Ley 1116)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.supersociedades",
            display_name="Supersociedades — Procesos de Insolvencia",
            description="Colombian insolvency proceedings under Ley 1116 (Superintendencia de Sociedades)",  # noqa: E501
            country="CO",
            url=SUPERSOCIEDADES_URL,
            supported_inputs=[DocumentType.NIT, DocumentType.CEDULA, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.document_number.strip()
        name = input.extra.get("name", "").strip()
        if not search_term and not name:
            raise SourceError("co.supersociedades", "Provide a NIT/cedula or name")

        query_term = search_term if search_term else name
        return self._query(query_term, audit=input.audit)

    def _query(self, query: str, audit: bool = False) -> SupersociedadesResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("co.supersociedades", "nit", query)

        with browser.page(SUPERSOCIEDADES_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(2000)

                # Find and fill search input
                search_input = page.query_selector(
                    'input[type="text"][id*="search"], '
                    'input[type="text"][id*="buscar"], '
                    'input[type="text"][id*="nit"], '
                    'input[type="search"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("co.supersociedades", "Could not find search input field")

                search_input.fill(query)
                logger.info("Searching Supersociedades for: %s", query)

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
                    search_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, query)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("co.supersociedades", f"Query failed: {e}") from e

    def _parse_result(self, page, query: str) -> SupersociedadesResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        result = SupersociedadesResult(
            queried_at=datetime.now(),
            documento=query,
        )

        # Try to extract from result tables
        rows = page.query_selector_all("table tr, .resultado, .item-resultado")

        procesos = []
        for row in rows:
            text = row.inner_text()
            if not text.strip():
                continue
            cells = text.split("\t")
            if len(cells) >= 2:
                procesos.append(
                    InsolvencyProceeding(
                        tipo_proceso=cells[0].strip() if cells else "",
                        estado=cells[1].strip() if len(cells) > 1 else "",
                        fecha_admision=cells[2].strip() if len(cells) > 2 else "",
                        juzgado=cells[3].strip() if len(cells) > 3 else "",
                        promotor=cells[4].strip() if len(cells) > 4 else "",
                    )
                )

        result.procesos = procesos
        result.total_procesos = len(procesos)
        result.tiene_proceso_insolvencia = len(procesos) > 0

        # Extract basic fields from page text
        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if "razón social" in lower and ":" in stripped:
                result.razon_social = stripped.split(":", 1)[1].strip()
            elif "nit" in lower and ":" in stripped and not result.nit:
                result.nit = stripped.split(":", 1)[1].strip()

        return result
