"""Nicaragua DGR source — tax registration lookup (Dirección General de Rentas).

Queries the DGI/DGR portal for taxpayer registration info by taxpayer name.
Browser-based, public, no authentication required.

Source: https://www.dgi.gob.ni/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ni.dgr import NiDgrResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

DGR_URL = "https://www.dgi.gob.ni/"


@register
class NiDgrSource(BaseSource):
    """Query Nicaragua DGR tax registry by taxpayer name."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ni.dgr",
            display_name="DGR — Dirección General de Rentas Nicaragua",
            description=(
                "Nicaragua DGR taxpayer registration lookup: name, tax status, and details "
                "(Dirección General de Rentas / DGI)"
            ),
            country="NI",
            url=DGR_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("taxpayer_name", "") or input.document_number
        if not search_term:
            raise SourceError("ni.dgr", "Taxpayer name is required")
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> NiDgrResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("ni.dgr", "taxpayer_name", search_term)

        with browser.page(DGR_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    '#txtNombre, input[name="txtNombre"], '
                    '#nombre, input[name="nombre"], '
                    'input[placeholder*="nombre"], input[placeholder*="Nombre"], '
                    'input[id*="contribuyente"], input[name*="contribuyente"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("ni.dgr", "Could not find taxpayer name input field")

                search_input.fill(search_term)
                logger.info("Filled taxpayer name: %s", search_term)

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
                raise SourceError("ni.dgr", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> NiDgrResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = NiDgrResult(queried_at=datetime.now(), search_term=search_term)

        field_map = {
            "nombre": "taxpayer_name",
            "razón social": "taxpayer_name",
            "razon social": "taxpayer_name",
            "contribuyente": "taxpayer_name",
            "estado": "tax_status",
            "situación": "tax_status",
            "situacion": "tax_status",
        }

        details: dict[str, str] = {}

        for line in body_text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            lower = stripped.lower()
            for label, field in field_map.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value:
                        setattr(result, field, value)
                    break
            if ":" in stripped:
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip()
                if key and val:
                    details[key] = val

        result.details = details
        return result
