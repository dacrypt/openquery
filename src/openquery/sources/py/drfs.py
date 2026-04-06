"""Paraguay DRFS source — company registry lookup.

Queries the Dirección del Registro de Personas Físicas y Jurídicas
for company registration status, series, folio, and type.

Source: https://drfs.abogacia.gov.py/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.py.drfs import PyDrfsResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

DRFS_URL = "https://drfs.abogacia.gov.py/"


@register
class PyDrfsSource(BaseSource):
    """Query Paraguayan DRFS company registry by name or registration number."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="py.drfs",
            display_name="DRFS — Registro de Personas Jurídicas",
            description="Paraguay company registry: registration status, folio, type (DRFS/Abogacía del Tesoro)",  # noqa: E501
            country="PY",
            url=DRFS_URL,
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
            raise SourceError("py.drfs", "Company name or registration number is required")
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> PyDrfsResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("py.drfs", "custom", search_term)

        with browser.page(DRFS_URL) as page:
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
                    raise SourceError("py.drfs", "Could not find search input field")

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
                raise SourceError("py.drfs", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> PyDrfsResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = PyDrfsResult(queried_at=datetime.now(), search_term=search_term)

        field_map = {
            "razon social": "company_name",
            "denominacion": "company_name",
            "nombre": "company_name",
            "estado": "registration_status",
            "situacion": "registration_status",
            "folio": "folio",
            "tipo": "company_type",
            "tipo de sociedad": "company_type",
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
