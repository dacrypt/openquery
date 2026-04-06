"""Defensor source — El Salvador consumer complaints.

Queries El Salvador Defensoría del Consumidor for consumer complaints
against companies by company name. Browser-based, no CAPTCHA.

URL: https://www.defensoria.gob.sv/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.sv.defensor import SvDefensorResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

DEFENSOR_URL = "https://www.defensoria.gob.sv/"


@register
class SvDefensorSource(BaseSource):
    """Query El Salvador Defensoría del Consumidor for company complaints."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="sv.defensor",
            display_name="Defensoría del Consumidor (SV)",
            description="El Salvador Defensoría del Consumidor: consumer complaints by company",
            country="SV",
            url=DEFENSOR_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("company_name", "") or input.document_number
        if not search_term:
            raise SourceError("sv.defensor", "Company name is required")
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> SvDefensorResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("sv.defensor", "company_name", search_term)

        with browser.page(DEFENSOR_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "page_loaded")

                search_input = page.query_selector(
                    "input[name*='empresa'], input[name*='proveedor'], input[name*='buscar'], "
                    "input[id*='empresa'], input[id*='buscar'], "
                    "input[placeholder*='empresa'], input[placeholder*='proveedor'], "
                    "input[type='text'], input[type='search']"
                )
                if not search_input:
                    raise SourceError("sv.defensor", "Could not find search input field")

                search_input.fill(search_term)
                logger.info("Querying Defensoría for company: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    "button[type='submit'], input[type='submit'], "
                    "button:has-text('Buscar'), button:has-text('Consultar')"
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
                raise SourceError("sv.defensor", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> SvDefensorResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = SvDefensorResult(queried_at=datetime.now(), search_term=search_term)

        field_patterns = {
            "empresa": "company_name",
            "proveedor": "company_name",
            "razón social": "company_name",
            "denuncias": "total_complaints",
            "quejas": "total_complaints",
            "reclamos": "total_complaints",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_patterns.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value:
                        if field == "company_name" and not result.company_name:
                            result.company_name = value
                        elif field == "total_complaints" and result.total_complaints == 0:
                            try:
                                result.total_complaints = int(value.replace(",", ""))
                            except ValueError:
                                pass
                    break

        rows = page.query_selector_all("table tr")
        if len(rows) >= 2:
            cells = rows[1].query_selector_all("td")
            if cells:
                values = [(c.inner_text() or "").strip() for c in cells]
                if len(values) >= 1 and not result.company_name:
                    result.company_name = values[0]

        result.details = {"raw": body_text.strip()[:500]}
        return result
