"""Uruguay DGR source — company/commerce registry lookup.

Queries Uruguay's Dirección General de Registros for company
registration status, type, and details by name or registration number.

Source: https://portal.dgr.gub.uy/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.uy.dgr import UyDgrResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

DGR_URL = "https://portal.dgr.gub.uy/"


@register
class UyDgrSource(BaseSource):
    """Query Uruguayan DGR company registry by name or registration number."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="uy.dgr",
            display_name="DGR — Registro de Comercio",
            description="Uruguay company/commerce registry: registration status, type, details (Dirección General de Registros)",  # noqa: E501
            country="UY",
            url=DGR_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (
            input.document_number
            or input.extra.get("company_name", "")
            or input.extra.get("registration_number", "")
        )
        if not search_term:
            raise SourceError("uy.dgr", "Company name or registration number is required")
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> UyDgrResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("uy.dgr", "custom", search_term)

        with browser.page(DGR_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[name*="nombre"], input[id*="nombre"], '
                    'input[name*="empresa"], input[id*="empresa"], '
                    'input[name*="razon"], input[name*="search"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("uy.dgr", "Could not find search input field")

                search_input.fill(search_term)
                logger.info("Filled search term: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button:has-text("Buscar"), button:has-text("Consultar")'
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
                raise SourceError("uy.dgr", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> UyDgrResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = UyDgrResult(queried_at=datetime.now(), search_term=search_term)

        field_map = {
            "razon social": "company_name",
            "denominacion": "company_name",
            "nombre": "company_name",
            "estado": "registration_status",
            "situacion": "registration_status",
            "tipo": "company_type",
            "tipo de empresa": "company_type",
            "forma juridica": "company_type",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_map.items():
                if label in lower and (":" in stripped or "\t" in stripped):
                    sep = ":" if ":" in stripped else "\t"
                    value = stripped.split(sep, 1)[1].strip()
                    if value and not getattr(result, field):
                        setattr(result, field, value)
                    break

        if body_text.strip():
            result.details = body_text.strip()[:500]

        return result
