"""Brazil ANVISA source — health product registry lookup.

Queries ANVISA portal for health product registrations by product name
or registration number.
Browser-based, public access.

Source: https://consultas.anvisa.gov.br/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.br.anvisa import AnvisaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

ANVISA_URL = "https://consultas.anvisa.gov.br/#/medicamentos/"


@register
class AnvisaSource(BaseSource):
    """Query ANVISA portal for health product registry status."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.anvisa",
            display_name="ANVISA — Consulta de Produtos Registrados",
            description="ANVISA health product registry lookup by product name or registration number",  # noqa: E501
            country="BR",
            url=ANVISA_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("search_term", "") or input.document_number
        if not search_term:
            raise SourceError(
                "br.anvisa", "Search term (product name or registration number) is required"
            )
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> AnvisaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("br.anvisa", "search_term", search_term)

        with browser.page(ANVISA_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(3000)

                search_input = page.query_selector(
                    'input[placeholder*="produto" i], input[placeholder*="registro" i], '
                    'input[name*="produto" i], input[id*="produto" i], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("br.anvisa", "Could not find search input field")

                search_input.fill(search_term)
                logger.info("Filled search term: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="consultar" i], button[id*="pesquisar" i]'
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
                raise SourceError("br.anvisa", f"Query failed: {e}") from e

    def _parse_result(self, page: object, search_term: str) -> AnvisaResult:
        from datetime import datetime

        body_text = page.inner_text("body")  # type: ignore[union-attr]
        body_lower = body_text.lower()
        product_name = ""
        registration_number = ""
        status = ""
        details: dict[str, str] = {}

        not_found_phrases = ("nenhum registro", "não encontrado", "sem resultado")
        if any(phrase in body_lower for phrase in not_found_phrases):
            return AnvisaResult(
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

                if any(k in lower for k in ("produto", "denominação", "nome")):
                    if not product_name and val_clean:
                        product_name = val_clean

                if any(k in lower for k in ("registro", "número", "numero")):
                    if not registration_number and val_clean:
                        registration_number = val_clean

                if any(k in lower for k in ("situação", "situacao", "status")):
                    if not status and val_clean:
                        status = val_clean

        return AnvisaResult(
            queried_at=datetime.now(),
            search_term=search_term,
            product_name=product_name,
            registration_number=registration_number,
            status=status,
            details=details,
        )
