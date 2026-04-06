"""Brazil TCU source — government audit sanctions (licitantes inidôneos).

Queries the TCU (Tribunal de Contas da União) portal for companies/individuals
declared ineligible for government contracting.

Portal: https://portal.tcu.gov.br/licitantes-inidoneos
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.br.tcu import BrTcuResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

TCU_URL = "https://portal.tcu.gov.br/licitantes-inidoneos"


@register
class BrTcuSource(BaseSource):
    """Query TCU inidoneidade (government sanctions) by company name or CNPJ."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.tcu",
            display_name="TCU — Licitantes Inidôneos (Sanções a Empresas)",
            description="TCU government sanctions registry — companies/persons ineligible for contracts",  # noqa: E501
            country="BR",
            url=TCU_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search = (
            input.extra.get("company_name", "")
            or input.extra.get("cnpj", "")
            or input.document_number
        ).strip()
        if not search:
            raise SourceError("br.tcu", "Company name or CNPJ is required")
        return self._query(search, audit=input.audit)

    def _query(self, search: str, audit: bool = False) -> BrTcuResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("br.tcu", "search", search)

        with browser.page(TCU_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=15000)

                # Find search input and fill
                search_input = page.query_selector(
                    'input[type="text"], input[type="search"], '
                    'input[name*="busca"], input[name*="search"], '
                    'input[id*="busca"], input[id*="search"]'
                )
                if search_input:
                    search_input.fill(search)
                    search_input.press("Enter")
                    page.wait_for_timeout(3000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("br.tcu", f"Query failed: {e}") from e

    def _parse_result(self, page, search: str) -> BrTcuResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        company_name = ""
        cnpj = ""
        sanction_status = "clear"

        if any(
            phrase in body_lower
            for phrase in ["inidôneo", "inidoneo", "declarad", "sancionad", "impedid"]
        ):
            sanction_status = "sanctioned"

        if "não foram encontrad" in body_lower or "nenhum resultado" in body_lower:
            sanction_status = "clear"

        # Try to extract company name and CNPJ from results
        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if ("razão social" in lower or "nome" in lower) and ":" in stripped:
                val = stripped.split(":", 1)[1].strip()
                if val and not company_name:
                    company_name = val
            elif ("cnpj" in lower or "cpf" in lower) and ":" in stripped:
                val = stripped.split(":", 1)[1].strip()
                if val and not cnpj:
                    cnpj = val

        return BrTcuResult(
            queried_at=datetime.now(),
            search_term=search,
            company_name=company_name,
            cnpj=cnpj,
            sanction_status=sanction_status,
        )
