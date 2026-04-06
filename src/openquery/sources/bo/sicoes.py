"""Bolivia SICOES source — government contracts portal.

Queries Bolivia's SICOES portal for tenders, contracts, and adjudications.

Source: https://www.sicoes.gob.bo/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.bo.sicoes import SicoesContract, SicoesResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SICOES_URL = "https://www.sicoes.gob.bo/"


@register
class SicoesSource(BaseSource):
    """Query Bolivia's SICOES government contracts portal by entity or contractor name."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="bo.sicoes",
            display_name="SICOES — Contratos del Estado",
            description=(
                "Bolivia government contracts: tenders, adjudications,"
                " contracts (Sistema de Contrataciones del Estado)"
            ),
            country="BO",
            url=SICOES_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (
            input.extra.get("entity_name", "")
            or input.extra.get("contractor_name", "")
            or input.document_number
        )
        if not search_term:
            raise SourceError("bo.sicoes", "entity_name or contractor_name is required")
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> SicoesResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("bo.sicoes", "search_term", search_term)

        with browser.page(SICOES_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[name*="search"], input[name*="Search"], '
                    'input[id*="search"], input[placeholder*="entidad"], '
                    'input[placeholder*="proveedor"], input[placeholder*="contrat"], '
                    'input[type="search"], input[type="text"]'
                )
                if not search_input:
                    raise SourceError("bo.sicoes", "Could not find search input field")

                search_input.fill(search_term)
                logger.info("Filled search term: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'input[type="submit"], button[type="submit"], '
                    'button:has-text("Buscar"), button:has-text("Consultar"), '
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
                raise SourceError("bo.sicoes", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> SicoesResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = SicoesResult(queried_at=datetime.now(), search_term=search_term)

        contracts: list[SicoesContract] = []

        # Try table rows first
        rows = page.query_selector_all("table tr")
        if rows:
            for row in rows[1:]:  # skip header
                cells = row.query_selector_all("td")
                if len(cells) >= 3:
                    texts = [c.inner_text().strip() for c in cells]
                    contract = SicoesContract(
                        code=texts[0] if len(texts) > 0 else "",
                        entity=texts[1] if len(texts) > 1 else "",
                        description=texts[2] if len(texts) > 2 else "",
                        amount=texts[3] if len(texts) > 3 else "",
                        status=texts[4] if len(texts) > 4 else "",
                        date=texts[5] if len(texts) > 5 else "",
                    )
                    contracts.append(contract)

        # Fallback: parse text lines for labelled fields
        if not contracts:
            current: dict[str, str] = {}
            for line in body_text.split("\n"):
                stripped = line.strip()
                lower = stripped.lower()
                if "código" in lower and ":" in stripped:
                    if current:
                        contracts.append(SicoesContract(**current))
                        current = {}
                    current["code"] = stripped.split(":", 1)[1].strip()
                elif "entidad" in lower and ":" in stripped:
                    current["entity"] = stripped.split(":", 1)[1].strip()
                elif "descripción" in lower and ":" in stripped:
                    current["description"] = stripped.split(":", 1)[1].strip()
                elif "monto" in lower and ":" in stripped:
                    current["amount"] = stripped.split(":", 1)[1].strip()
                elif "estado" in lower and ":" in stripped:
                    current["status"] = stripped.split(":", 1)[1].strip()
                elif "fecha" in lower and ":" in stripped:
                    current["date"] = stripped.split(":", 1)[1].strip()
            if current:
                contracts.append(SicoesContract(**current))

        result.contracts = contracts
        result.total = len(contracts)
        return result
