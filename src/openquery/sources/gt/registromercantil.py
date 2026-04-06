"""Guatemala Registro Mercantil source — company registry.

Queries Guatemala's Registro Mercantil for company data
by company name or registration number.

Flow:
1. Navigate to eregistros.registromercantil.gob.gt
2. Enter company name or registration number
3. Submit and parse registration status, folio, type

Source: https://eregistros.registromercantil.gob.gt/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.gt.registromercantil import GtRegistroMercantilResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

REGISTRO_MERCANTIL_URL = "https://eregistros.registromercantil.gob.gt/"


@register
class GtRegistroMercantilSource(BaseSource):
    """Query Guatemala Registro Mercantil company registry by name or registration number."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="gt.registromercantil",
            display_name="Registro Mercantil — Consulta de Empresas Guatemala",
            description="Guatemala company registry: registration status, folio, type (Registro Mercantil)",  # noqa: E501
            country="GT",
            url=REGISTRO_MERCANTIL_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("search_term", "") or input.document_number
        if not search_term:
            raise SourceError("gt.registromercantil", "search_term or document_number is required")
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> GtRegistroMercantilResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("gt.registromercantil", "search_term", search_term)

        with browser.page(REGISTRO_MERCANTIL_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill search input
                search_input = page.query_selector(
                    'input[id*="empresa"], input[name*="empresa"], '
                    'input[id*="razon"], input[name*="razon"], '
                    'input[id*="buscar"], input[name*="buscar"], '
                    'input[id*="search"], input[name*="search"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("gt.registromercantil", "Could not find search input field")

                search_input.fill(search_term)
                logger.info("Filled search term: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="consultar"], button[id*="buscar"], '
                    'button:has-text("Consultar"), button:has-text("Buscar")'
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
                raise SourceError("gt.registromercantil", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> GtRegistroMercantilResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = GtRegistroMercantilResult(queried_at=datetime.now(), search_term=search_term)
        details: dict[str, str] = {}

        field_map = {
            "razon social": "company_name",
            "razón social": "company_name",
            "empresa": "company_name",
            "nombre": "company_name",
            "estado": "registration_status",
            "folio": "folio",
            "tipo": "company_type",
            "sociedad": "company_type",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            lower = stripped.lower()
            for label, attr in field_map.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value:
                        setattr(result, attr, value)
                    break
            # Collect all key:value pairs into details
            if ":" in stripped:
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip()
                if key and val:
                    details[key] = val

        result.details = details
        return result
