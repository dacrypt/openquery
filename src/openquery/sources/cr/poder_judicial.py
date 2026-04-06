"""Costa Rica Poder Judicial court cases source.

Queries the Poder Judicial online consultation portal for court case information.
Browser-based, public tier, no authentication required for basic case info.

Source: https://pj.poder-judicial.go.cr/index.php/consultas-en-linea
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.cr.poder_judicial import CrPoderJudicialResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

PODER_JUDICIAL_URL = "https://pj.poder-judicial.go.cr/index.php/consultas-en-linea"


@register
class CrPoderJudicialSource(BaseSource):
    """Query Costa Rica Poder Judicial court cases by case number or party cedula."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="cr.poder_judicial",
            display_name="Poder Judicial — Consultas en Línea",
            description=(
                "Costa Rica court case lookup: case status, parties, court, "
                "and resolution dates (Poder Judicial)"
            ),
            country="CR",
            url=PODER_JUDICIAL_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_value = input.extra.get("case_number", "") or input.document_number
        if not search_value:
            raise SourceError("cr.poder_judicial", "Case number or cedula is required")
        return self._query(search_value.strip(), audit=input.audit)

    def _query(self, search_value: str, audit: bool = False) -> CrPoderJudicialResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("cr.poder_judicial", "search_value", search_value)

        with browser.page(PODER_JUDICIAL_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    '#txtExpediente, input[name="txtExpediente"], '
                    '#txtCedula, input[name="txtCedula"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("cr.poder_judicial", "Could not find search input field")

                search_input.fill(search_value)
                logger.info("Filled search value: %s", search_value)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    '#btnConsultar, input[name="btnConsultar"], '
                    '#btnBuscar, input[name="btnBuscar"], '
                    'button[type="submit"]'
                )
                if submit:
                    submit.click()
                else:
                    search_input.press("Enter")

                page.wait_for_timeout(3000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_value)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("cr.poder_judicial", f"Query failed: {e}") from e

    def _parse_result(self, page, search_value: str) -> CrPoderJudicialResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        result = CrPoderJudicialResult(
            queried_at=datetime.now(),
            search_value=search_value,
        )

        field_patterns = {
            "expediente": "case_number",
            "número de expediente": "case_number",
            "despacho": "court",
            "juzgado": "court",
            "tribunal": "court",
            "estado": "status",
            "etapa": "status",
            "partes": "parties",
            "demandante": "parties",
            "actor": "parties",
            "fecha de entrada": "filing_date",
            "fecha entrada": "filing_date",
            "ingreso": "filing_date",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_patterns.items():
                if lower.startswith(label) and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value:
                        setattr(result, field, value)
                    break

        result.details = body_text.strip()[:500]

        return result
