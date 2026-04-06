"""Brazil CVM source — securities regulator company/fund lookup.

Queries CVM RAD portal for registered companies and funds by company
name or CNPJ.
Browser-based, public access.

Source: https://www.rad.cvm.gov.br/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.br.cvm import CvmResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CVM_URL = "https://www.rad.cvm.gov.br/ENET/frmConsultaExternaCVM.aspx"


@register
class CvmSource(BaseSource):
    """Query CVM RAD portal for registered companies and funds."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.cvm",
            display_name="CVM — Consulta de Companhias e Fundos",
            description="CVM securities regulator lookup for registered companies and funds by name or CNPJ",  # noqa: E501
            country="BR",
            url=CVM_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("search_term", "") or input.document_number
        if not search_term:
            raise SourceError("br.cvm", "Search term (company name or CNPJ) is required")
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> CvmResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("br.cvm", "search_term", search_term)

        with browser.page(CVM_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[id*="txtNomeEmpresa" i], input[name*="nomeEmpresa" i], '
                    'input[id*="txtCNPJ" i], input[name*="cnpj" i], '
                    'input[placeholder*="empresa" i], input[placeholder*="cnpj" i], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("br.cvm", "Could not find search input field")

                search_input.fill(search_term)
                logger.info("Filled search term: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'input[type="submit"], button[type="submit"], '
                    'input[value*="Consultar"], button[id*="consultar" i]'
                )
                if submit:
                    submit.click()
                else:
                    search_input.press("Enter")

                page.wait_for_load_state("networkidle", timeout=30000)
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
                raise SourceError("br.cvm", f"Query failed: {e}") from e

    def _parse_result(self, page: object, search_term: str) -> CvmResult:
        from datetime import datetime

        body_text = page.inner_text("body")  # type: ignore[union-attr]
        body_lower = body_text.lower()
        company_name = ""
        cnpj = ""
        registration_status = ""
        details: dict[str, str] = {}

        not_found_phrases = ("nenhuma empresa", "não encontrado", "sem resultado")
        if any(phrase in body_lower for phrase in not_found_phrases):
            return CvmResult(
                queried_at=datetime.now(),
                search_term=search_term,
            )

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if not stripped:
                continue

            if ":" in stripped:
                key, _, val = stripped.partition(":")
                key_clean = key.strip()
                val_clean = val.strip()
                if val_clean:
                    details[key_clean] = val_clean

                if any(k in lower for k in ("empresa", "companhia", "fundo", "razão")):
                    if not company_name and val_clean:
                        company_name = val_clean

                if "cnpj" in lower:
                    if not cnpj and val_clean:
                        cnpj = val_clean

                if any(k in lower for k in ("situação", "situacao", "status", "registro")):
                    if not registration_status and val_clean:
                        registration_status = val_clean

        return CvmResult(
            queried_at=datetime.now(),
            search_term=search_term,
            company_name=company_name,
            cnpj=cnpj,
            registration_status=registration_status,
            details=details,
        )
