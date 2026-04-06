"""Nicaragua MIFIC trade/industry registry source.

Queries MIFIC (Ministerio de Fomento, Industria y Comercio) for
trade and industry registration data by company name.

URL: https://www.mific.gob.ni/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ni.mific import NiMificResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

MIFIC_URL = "https://www.mific.gob.ni/"


@register
class NiMificSource(BaseSource):
    """Query Nicaragua MIFIC for trade and industry registration data."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ni.mific",
            display_name="MIFIC — Registro Comercio e Industria Nicaragua",
            description=(
                "Nicaragua MIFIC trade/industry registry: company registration "
                "status and details by company name"
            ),
            country="NI",
            url=MIFIC_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query MIFIC for trade/industry registration data."""
        search_term = input.extra.get("company_name", "") or input.document_number
        if not search_term:
            raise SourceError("ni.mific", "company_name is required")
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> NiMificResult:
        """Full flow: launch browser, fill form, parse results."""
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("ni.mific", "company_name", search_term)

        with browser.page(MIFIC_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[id*="empresa"], input[name*="empresa"], '
                    'input[id*="comercio"], input[name*="comercio"], '
                    'input[id*="nombre"], input[name*="nombre"], '
                    'input[id*="search"], input[name*="search"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("ni.mific", "Could not find search input field")

                search_input.fill(search_term)
                logger.info("Filled search term: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    '#btnBuscar, input[name="btnBuscar"], '
                    'button:has-text("Buscar"), button:has-text("Consultar")'
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
                raise SourceError("ni.mific", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> NiMificResult:
        """Parse trade/industry registration data from the page DOM."""
        body_text = page.inner_text("body")
        result = NiMificResult(search_term=search_term)
        details: dict[str, str] = {}

        field_map = {
            "company name": "company_name",
            "nombre de la empresa": "company_name",
            "nombre de empresa": "company_name",
            "nombre comercial": "company_name",
            "nombre": "company_name",
            "registration status": "registration_status",
            "estado de registro": "registration_status",
            "estado del registro": "registration_status",
            "estado": "registration_status",
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
            if ":" in stripped:
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip()
                if key and val:
                    details[key] = val

        result.details = details
        logger.info(
            "MIFIC result — company=%s, status=%s",
            result.company_name,
            result.registration_status,
        )
        return result
