"""Honduras company registry source — Registro Mercantil CCICH.

Queries Honduras' Cámara de Comercio e Industrias de Cortés (CCICH)
company registry for business registration data.

Source: https://registromercantil.ccichonduras.org/app/consulta-registro-mercantil/Consulta_de_empresas.htm
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.hn.empresa import HnEmpresaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

EMPRESA_URL = (
    "https://registromercantil.ccichonduras.org/app/consulta-registro-mercantil/"
    "Consulta_de_empresas.htm"
)


@register
class HnEmpresaSource(BaseSource):
    """Query Honduras company registry (Registro Mercantil) by name or RTN."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="hn.empresa",
            display_name="Registro Mercantil Honduras — CCICH",
            description=(
                "Honduras company registry: name, type, registration date, legal rep (CCICH)"
            ),
            country="HN",
            url=EMPRESA_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (
            input.extra.get("company_name", "")
            or input.extra.get("rtn", "")
            or input.document_number
        )
        if not search_term:
            raise SourceError("hn.empresa", "company_name or rtn is required")
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> HnEmpresaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("hn.empresa", "search_term", search_term)

        with browser.page(EMPRESA_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill search input
                search_input = page.query_selector(
                    'input[id*="nombre"], input[name*="nombre"], '
                    'input[id*="empresa"], input[name*="empresa"], '
                    'input[id*="rtn"], input[name*="rtn"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("hn.empresa", "Could not find search input field")

                search_input.fill(search_term)
                logger.info("Filled search term: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button:has-text("Consultar"), button:has-text("Buscar"), '
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
                raise SourceError("hn.empresa", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> HnEmpresaResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = HnEmpresaResult(queried_at=datetime.now(), search_term=search_term)
        details: dict[str, str] = {}

        field_map = {
            "nombre": "company_name",
            "razón social": "company_name",
            "razon social": "company_name",
            "tipo": "company_type",
            "fecha": "registration_date",
            "representante": "legal_representative",
            "apoderado": "legal_representative",
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
