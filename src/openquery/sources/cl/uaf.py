"""UAF source — Chilean financial intelligence designated persons list.

Queries the UAF (Unidad de Analisis Financiero) for designated persons.

Flow:
1. Navigate to UAF consultation page
2. Enter name to check
3. Parse result for designation status

Source: https://www.uaf.cl/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.cl.uaf import UafResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

UAF_URL = "https://www.uaf.cl/legislacion/personas_designadas.aspx"


@register
class UafSource(BaseSource):
    """Query Chilean financial intelligence designated persons list (UAF)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="cl.uaf",
            display_name="UAF Chile — Personas Designadas",
            description="Chilean financial intelligence designated persons list (UAF)",
            country="CL",
            url=UAF_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("name") or input.document_number
        if not search_term:
            raise SourceError("cl.uaf", "name is required")
        return self._query(search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> UafResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("cl.uaf", "custom", search_term)

        with browser.page(UAF_URL) as page:
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
                    raise SourceError("cl.uaf", "Could not find search input field")

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
                raise SourceError("cl.uaf", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> UafResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        is_designated = any(
            phrase in body_lower
            for phrase in ["designado", "listado", "encontrado", "persona designada"]
        )

        no_results = any(
            phrase in body_lower
            for phrase in [
                "no se encontr",
                "no registra",
                "sin resultados",
                "no result",
            ]
        )

        if no_results:
            is_designated = False

        return UafResult(
            queried_at=datetime.now(),
            search_term=search_term,
            is_designated=is_designated,
            details={"source": "UAF Chile"},
        )
