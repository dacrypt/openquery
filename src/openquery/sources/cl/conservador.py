"""Conservador source — Chile property registry (Conservador de Bienes Raíces).

Queries Chile's Conservador de Bienes Raíces for property records and mortgages.

Flow:
1. Navigate to the Conservador online consultation portal
2. Enter surnames and municipality
3. Submit and parse property records and mortgage data

Source: https://conservador.cl/portal/consultas_en_linea
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.cl.conservador import ConservadorResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CONSERVADOR_URL = "https://conservador.cl/portal/consultas_en_linea"


@register
class ConservadorSource(BaseSource):
    """Query Chile's Conservador de Bienes Raíces property records."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="cl.conservador",
            display_name="Conservador de Bienes Raíces",
            description="Chile property registry: property records and mortgages by name and municipality",  # noqa: E501
            country="CL",
            url=CONSERVADOR_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CUSTOM:
            raise SourceError("cl.conservador", f"Unsupported input type: {input.document_type}")

        name = input.extra.get("name", "").strip()
        municipality = input.extra.get("municipality", "").strip()

        if not name and not municipality:
            raise SourceError(
                "cl.conservador", "Must provide extra['name'] or extra['municipality']"
            )

        search_term = " ".join(filter(None, [name, municipality]))
        return self._query(
            name=name, municipality=municipality, search_term=search_term, audit=input.audit
        )

    def _query(
        self,
        name: str = "",
        municipality: str = "",
        search_term: str = "",
        audit: bool = False,
    ) -> ConservadorResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("cl.conservador", "nombre", search_term)

        with browser.page(CONSERVADOR_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                if name:
                    name_input = page.query_selector(
                        'input[id*="nombre"], input[name*="nombre"], '
                        'input[id*="apellido"], input[name*="apellido"], '
                        'input[placeholder*="nombre" i], input[type="text"]'
                    )
                    if name_input:
                        name_input.fill(name)
                        logger.info("Filled name: %s", name)

                if municipality:
                    muni_input = page.query_selector(
                        'input[id*="comuna"], input[name*="comuna"], '
                        'input[id*="municipio"], input[name*="municipio"], '
                        'select[id*="comuna"], select[name*="comuna"]'
                    )
                    if muni_input:
                        tag = muni_input.evaluate("el => el.tagName.toLowerCase()")
                        if tag == "select":
                            muni_input.select_option(label=municipality)
                        else:
                            muni_input.fill(municipality)
                        logger.info("Filled municipality: %s", municipality)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button:has-text("Buscar"), button:has-text("Consultar")'
                )
                if submit:
                    submit.click()
                else:
                    page.keyboard.press("Enter")

                page.wait_for_timeout(5000)
                page.wait_for_selector("body", timeout=15000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_term)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("cl.conservador", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> ConservadorResult:
        from datetime import datetime

        result = ConservadorResult(queried_at=datetime.now(), search_term=search_term)
        property_records: list[dict] = []
        mortgages: list[dict] = []
        details: dict = {}

        # Parse table rows into property records
        tables = page.query_selector_all("table")
        for table in tables:
            headers_els = table.query_selector_all("thead th, tr:first-child th, tr:first-child td")
            headers = [el.inner_text().strip() for el in headers_els]
            body_rows = table.query_selector_all("tbody tr, tr:not(:first-child)")
            for row in body_rows:
                cells = row.query_selector_all("td")
                if not cells:
                    continue
                row_data = {
                    (headers[i] if i < len(headers) else str(i)): cells[i].inner_text().strip()
                    for i in range(len(cells))
                }
                row_text = " ".join(row_data.values()).lower()
                if "hipoteca" in row_text or "gravamen" in row_text:
                    mortgages.append(row_data)
                else:
                    property_records.append(row_data)

        if property_records:
            result.property_records = property_records
        if mortgages:
            result.mortgages = mortgages
        if details:
            result.details = details

        return result
