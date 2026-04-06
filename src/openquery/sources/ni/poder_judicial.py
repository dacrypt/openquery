"""Nicaragua Poder Judicial source — NICARAO court cases.

Queries the NICARAO system for court case information by party name,
file number, or case number.
Browser-based, public, no authentication required.

Source: https://consultascausas.poderjudicial.gob.ni/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ni.poder_judicial import NiPoderJudicialResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

NICARAO_URL = "https://consultascausas.poderjudicial.gob.ni/"


@register
class NiPoderJudicialSource(BaseSource):
    """Query Nicaragua NICARAO court cases by party name, file number, or case number."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ni.poder_judicial",
            display_name="Poder Judicial — NICARAO Consulta de Causas",
            description=(
                "Nicaragua NICARAO court case lookup: case status, court, and region "
                "(Poder Judicial de Nicaragua)"
            ),
            country="NI",
            url=NICARAO_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (
            input.extra.get("case_number", "")
            or input.extra.get("party_name", "")
            or input.document_number
        )
        if not search_term:
            raise SourceError(
                "ni.poder_judicial", "Case number, file number, or party name is required"
            )
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> NiPoderJudicialResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("ni.poder_judicial", "case_number", search_term)

        with browser.page(NICARAO_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    '#txtExpediente, input[name="txtExpediente"], '
                    '#txtCausa, input[name="txtCausa"], '
                    '#txtBusqueda, input[name="txtBusqueda"], '
                    'input[placeholder*="expediente"], input[placeholder*="causa"]'
                )
                if not search_input:
                    raise SourceError("ni.poder_judicial", "Could not find search input field")

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
                raise SourceError("ni.poder_judicial", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> NiPoderJudicialResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = NiPoderJudicialResult(queried_at=datetime.now(), search_term=search_term)

        field_map = {
            "expediente": "case_number",
            "número de causa": "case_number",
            "juzgado": "court",
            "tribunal": "court",
            "estado": "status",
            "circunscripción": "region",
            "circunscripcion": "region",
            "región": "region",
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
