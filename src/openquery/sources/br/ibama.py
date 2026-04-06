"""IBAMA environmental sanctions source — Brazil.

Queries IBAMA for environmental fines by CPF/CNPJ.

URL: https://www.ibama.gov.br/
Input: CPF or CNPJ (custom)
Returns: environmental fines
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.br.ibama import IbamaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

IBAMA_URL = "https://consultas.ibama.gov.br/autuacoes"


@register
class IbamaSource(BaseSource):
    """Query IBAMA environmental fines by CPF/CNPJ."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.ibama",
            display_name="IBAMA — Autuações e Multas Ambientais",
            description="Brazil IBAMA environmental fines and sanctions lookup by CPF/CNPJ",
            country="BR",
            url=IBAMA_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("cpf_cnpj", input.document_number).strip()
        if not search_term:
            raise SourceError(
                "br.ibama",
                "Provide a CPF or CNPJ (extra.cpf_cnpj or document_number)",
            )
        return self._fetch(search_term, audit=input.audit)

    def _fetch(self, search_term: str, audit: bool = False) -> IbamaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying IBAMA: search_term=%s", search_term)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(IBAMA_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)
                page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                doc_input = page.query_selector(
                    "input[name*='cpf'], input[name*='cnpj'], input[id*='cpf'], "
                    "input[id*='cnpj'], input[type='text']"
                )
                if doc_input:
                    doc_input.fill(search_term)
                    submit = page.query_selector("button[type='submit'], input[type='submit']")
                    if submit:
                        submit.click()
                    else:
                        doc_input.press("Enter")
                    page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                body_text = page.inner_text("body")

                total_fines = 0
                fine_amount = ""

                rows = page.query_selector_all("table tbody tr, .result-row")
                total_fines = len(rows)

                for line in body_text.split("\n"):
                    line_lower = line.lower()
                    if "valor" in line_lower or "multa" in line_lower:
                        parts = line.split(":")
                        if len(parts) > 1 and not fine_amount:
                            fine_amount = parts[1].strip()

            return IbamaResult(
                queried_at=datetime.now(),
                search_term=search_term,
                total_fines=total_fines,
                fine_amount=fine_amount,
                details=f"IBAMA query for: {search_term}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("br.ibama", f"Query failed: {e}") from e
