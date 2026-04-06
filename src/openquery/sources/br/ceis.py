"""CEIS source — Brazilian sanctioned companies registry.

Queries the Portal Transparencia CEIS (Cadastro de Empresas Inidoneas e Suspensas)
for company sanction status.

Flow:
1. Navigate to Portal Transparencia CEIS page
2. Enter CNPJ or company name
3. Parse result for sanction status

Source: https://www.portaltransparencia.gov.br/sancoes/ceis
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.br.ceis import CeisResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CEIS_URL = "https://www.portaltransparencia.gov.br/sancoes/ceis"


@register
class CeisSource(BaseSource):
    """Query Brazilian sanctioned companies registry (CEIS)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.ceis",
            display_name="CEIS — Cadastro de Empresas Inidoneas e Suspensas",
            description="Brazilian sanctioned companies registry (Portal Transparencia CEIS)",
            country="BR",
            url=CEIS_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (
            input.extra.get("cnpj")
            or input.extra.get("company_name")
            or input.document_number
        )
        if not search_term:
            raise SourceError("br.ceis", "cnpj or company_name is required")
        return self._query(search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> CeisResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("br.ceis", "custom", search_term)

        with browser.page(CEIS_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[type="text"], input[type="search"], '
                    'input[id*="cnpj"], input[id*="nome"], input[id*="buscar"]'
                )
                if not search_input:
                    raise SourceError("br.ceis", "Could not find search input field")

                search_input.fill(search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="buscar"], button[id*="pesquisar"]'
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
                raise SourceError("br.ceis", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> CeisResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        company_name = ""
        cnpj = ""
        sanction_status = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if not stripped:
                continue
            if ("nome" in lower or "razao" in lower) and ":" in stripped:
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not company_name:
                    company_name = parts[1].strip()
            elif "cnpj" in lower and ":" in stripped:
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not cnpj:
                    cnpj = parts[1].strip()
            elif ("sancao" in lower or "situacao" in lower or "status" in lower) and ":" in stripped:  # noqa: E501
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not sanction_status:
                    sanction_status = parts[1].strip()

        is_sanctioned = any(
            phrase in body_lower
            for phrase in ["sancionado", "impedido", "suspenso", "inidone"]
        )

        no_results = any(
            phrase in body_lower
            for phrase in ["nenhum resultado", "nao encontrado", "0 resultado"]
        )

        if no_results:
            is_sanctioned = False

        if not sanction_status:
            sanction_status = "Sancionado" if is_sanctioned else "Nao encontrado"

        return CeisResult(
            queried_at=datetime.now(),
            search_term=search_term,
            company_name=company_name,
            cnpj=cnpj,
            sanction_status=sanction_status,
            details={"is_sanctioned": is_sanctioned},
        )
