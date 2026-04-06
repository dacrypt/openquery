"""SUSEP source — Brazil insurance regulator.

Queries the SUSEP (Superintendência de Seguros Privados) for
insurance company and intermediary data.

Source: https://www.susep.gov.br/
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.br.susep import SusepResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SUSEP_URL = "https://www.susep.gov.br/"
SUSEP_API_URL = "https://www2.susep.gov.br/menuatendimento/SusepConsulta/consultaEmpresas.action"


@register
class SusepSource(BaseSource):
    """Query Brazilian insurance regulator (SUSEP) company registry."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.susep",
            display_name="SUSEP — Seguros Privados",
            description="Brazilian insurance regulator: company registration, CNPJ, and authorization status",  # noqa: E501
            country="BR",
            url=SUSEP_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (
            input.extra.get("cnpj", "")
            or input.extra.get("company_name", "")
            or input.document_number
        ).strip()
        if not search_term:
            raise SourceError("br.susep", "CNPJ or company name required (pass via extra.cnpj, extra.company_name, or document_number)")  # noqa: E501
        return self._query(search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> SusepResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("br.susep", "cnpj_name", search_term)

        with browser.page(SUSEP_API_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(2000)

                search_input = page.locator(
                    'input[name*="cnpj"], input[name*="empresa"], '
                    'input[id*="cnpj"], input[placeholder*="CNPJ"], '
                    'input[type="text"]'
                ).first
                if search_input:
                    search_input.fill(search_term)
                    logger.info("Querying SUSEP for: %s", search_term[:4] + "***")

                    submit_btn = page.locator('button[type="submit"], input[type="submit"], input[value*="Pesquisar"]').first  # noqa: E501
                    if submit_btn:
                        submit_btn.click()
                    else:
                        search_input.press("Enter")

                    page.wait_for_timeout(4000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_term)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("br.susep", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> SusepResult:
        body_text = page.inner_text("body")
        result = SusepResult(queried_at=datetime.now(), search_term=search_term)

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if "razão social" in lower and ":" in stripped and not result.company_name:
                result.company_name = stripped.split(":", 1)[1].strip()
            elif "cnpj" in lower and ":" in stripped and not result.cnpj:
                result.cnpj = stripped.split(":", 1)[1].strip()
            elif "situação" in lower and ":" in stripped and not result.status:
                result.status = stripped.split(":", 1)[1].strip()

        return result
