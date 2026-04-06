"""El Salvador company registry source — CNR.

Queries El Salvador's Centro Nacional de Registros (CNR) for
company registration data by name or NIT/DUI.

Source: https://www.e.cnr.gob.sv/ServiciosOL/portada/rco.htm
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.sv.empresa import SvEmpresaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CNR_URL = "https://www.e.cnr.gob.sv/ServiciosOL/portada/rco.htm"


@register
class SvEmpresaSource(BaseSource):
    """Query El Salvador company registry (CNR) by name or NIT/DUI."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="sv.empresa",
            display_name="CNR — Registro de Comercio El Salvador",
            description="El Salvador company registry: name, type, status, partners (CNR)",
            country="SV",
            url=CNR_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (
            input.extra.get("company_name", "")
            or input.extra.get("nit", "")
            or input.extra.get("dui", "")
            or input.document_number
        )
        if not search_term:
            raise SourceError("sv.empresa", "company_name, nit, or dui is required")
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> SvEmpresaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("sv.empresa", "search_term", search_term)

        with browser.page(CNR_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill search input
                search_input = page.query_selector(
                    'input[id*="nombre"], input[name*="nombre"], '
                    'input[id*="empresa"], input[name*="empresa"], '
                    'input[id*="nit"], input[name*="nit"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("sv.empresa", "Could not find search input field")

                search_input.fill(search_term)
                logger.info("Filled search term: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button:has-text("Consultar"), button:has-text("Buscar"), '
                    'a:has-text("Buscar")'
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
                raise SourceError("sv.empresa", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> SvEmpresaResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = SvEmpresaResult(queried_at=datetime.now(), search_term=search_term)
        details: dict[str, str] = {}

        field_map = {
            "nombre": "company_name",
            "razón social": "company_name",
            "razon social": "company_name",
            "tipo": "registration_type",
            "clase": "registration_type",
            "estado": "status",
            "situación": "status",
            "situacion": "status",
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
        return result
