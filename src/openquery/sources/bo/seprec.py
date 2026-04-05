"""Bolivia SEPREC source — company registry (Registro de Comercio).

Queries Bolivia's SEPREC portal for company registration data.

Source: https://miempresa.seprec.gob.bo/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.bo.seprec import SeprecResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SEPREC_URL = "https://miempresa.seprec.gob.bo/"


@register
class SeprecSource(BaseSource):
    """Query Bolivia's SEPREC company registry by company name or NIT."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="bo.seprec",
            display_name="SEPREC — Registro de Comercio",
            description=(
                "Bolivia company registry: business name, registration status,"
                " folio, legal representative"
            ),
            country="BO",
            url=SEPREC_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (
            input.extra.get("company_name", "")
            or input.extra.get("nit", "")
            or input.document_number
        )
        if not search_term:
            raise SourceError("bo.seprec", "company_name or NIT is required")
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> SeprecResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("bo.seprec", "search_term", search_term)

        with browser.page(SEPREC_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[name*="search"], input[name*="Search"], '
                    'input[id*="search"], input[placeholder*="empresa"], '
                    'input[placeholder*="NIT"], input[type="search"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("bo.seprec", "Could not find search input field")

                search_input.fill(search_term)
                logger.info("Filled search term: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'input[type="submit"], button[type="submit"], '
                    'button:has-text("Buscar"), button:has-text("Consultar"), '
                    'button:has-text("Search")'
                )
                if submit:
                    submit.click()
                else:
                    search_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_term)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("bo.seprec", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> SeprecResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = SeprecResult(queried_at=datetime.now(), search_term=search_term)

        field_map = {
            "razón social": "company_name",
            "razon social": "company_name",
            "nombre": "company_name",
            "nit": "nit",
            "estado": "registration_status",
            "folio": "folio",
            "representante legal": "legal_representative",
            "representante": "legal_representative",
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

        return result
