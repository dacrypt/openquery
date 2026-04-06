"""PGFN source — Brazil tax debt registry (Dívida Ativa).

Queries the PGFN (Procuradoria-Geral da Fazenda Nacional) regularize
portal for active tax debt (Dívida Ativa da União).

Source: https://www.regularize.pgfn.gov.br/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.br.pgfn import PgfnResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

PGFN_URL = "https://www.regularize.pgfn.gov.br/"


@register
class PgfnSource(BaseSource):
    """Query Brazilian federal tax debt registry (PGFN Dívida Ativa)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.pgfn",
            display_name="PGFN — Dívida Ativa da União",
            description="Brazilian federal tax debt registry: active debt status and total (PGFN)",
            country="BR",
            url=PGFN_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (
            input.extra.get("cpf", "")
            or input.extra.get("cnpj", "")
            or input.document_number
        ).strip()
        if not search_term:
            raise SourceError("br.pgfn", "CPF or CNPJ required (pass via extra.cpf, extra.cnpj, or document_number)")  # noqa: E501
        return self._query(search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> PgfnResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("br.pgfn", "cpf_cnpj", search_term)

        with browser.page(PGFN_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(2000)

                doc_input = page.locator(
                    'input[name*="cpf"], input[name*="cnpj"], '
                    'input[id*="cpf"], input[id*="cnpj"], '
                    'input[placeholder*="CPF"], input[placeholder*="CNPJ"], '
                    'input[type="text"]'
                ).first
                if doc_input:
                    doc_input.fill(search_term)
                    logger.info("Querying PGFN for: %s", search_term[:4] + "***")

                    submit_btn = page.locator('button[type="submit"], input[type="submit"], button:has-text("Consultar")').first  # noqa: E501
                    if submit_btn:
                        submit_btn.click()
                    else:
                        doc_input.press("Enter")

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
                raise SourceError("br.pgfn", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> PgfnResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = PgfnResult(queried_at=datetime.now(), search_term=search_term)

        lower_body = body_text.lower()
        if "sem débito" in lower_body or "sem divida" in lower_body or "regularizado" in lower_body:
            result.debt_status = "Sem débito"
        elif "débito" in lower_body or "divida" in lower_body:
            result.debt_status = "Com débito"

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if "total" in lower and ":" in stripped and not result.total_debt:
                result.total_debt = stripped.split(":", 1)[1].strip()
            elif "situação" in lower and ":" in stripped and not result.debt_status:
                result.debt_status = stripped.split(":", 1)[1].strip()

        return result
