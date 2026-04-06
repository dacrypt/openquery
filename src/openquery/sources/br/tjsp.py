"""Brazil TJSP source — São Paulo court cases lookup.

Queries TJSP eSAJ portal for court cases by party name or case number.
Browser-based, public access.

Source: https://esaj.tjsp.jus.br/cjpg/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.br.tjsp import TjspResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

TJSP_URL = "https://esaj.tjsp.jus.br/cjpg/pesquisar.do"


@register
class TjspSource(BaseSource):
    """Query TJSP São Paulo portal for court cases."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.tjsp",
            display_name="TJSP — Consulta de Processos (São Paulo)",
            description="São Paulo court case lookup by party name or case number (TJSP eSAJ)",
            country="BR",
            url=TJSP_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("search_term", "") or input.document_number
        if not search_term:
            raise SourceError("br.tjsp", "Search term (party name or case number) is required")
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> TjspResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("br.tjsp", "search_term", search_term)

        with browser.page(TJSP_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[name*="nmParticipante" i], input[name*="nomeParticipante" i], '
                    'input[id*="nomeParticipante" i], input[name*="processo" i], '
                    'input[id*="numeroDigitoAnoUnificado" i], '
                    'textarea[name*="dadosConsulta.pesquisaLivre"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("br.tjsp", "Could not find search input field")

                search_input.fill(search_term)
                logger.info("Filled search term: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'input[type="submit"][value*="Pesquisar"], '
                    'button[type="submit"], input[type="submit"]'
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
                raise SourceError("br.tjsp", f"Query failed: {e}") from e

    def _parse_result(self, page: object, search_term: str) -> TjspResult:
        import re
        from datetime import datetime

        body_text = page.inner_text("body")  # type: ignore[union-attr]
        body_lower = body_text.lower()
        cases: list[dict[str, str]] = []
        total_cases = 0
        details: dict[str, str] = {}

        not_found_phrases = ("nenhum processo", "não foram encontrados", "sem resultado")
        if any(phrase in body_lower for phrase in not_found_phrases):
            return TjspResult(
                queried_at=datetime.now(),
                search_term=search_term,
                total_cases=0,
                cases=[],
                details=details,
            )

        # Try to find total count from result header
        total_match = re.search(r"(\d+)\s*processo", body_lower)
        if total_match:
            total_cases = int(total_match.group(1))

        # Extract case rows from table
        try:
            rows = page.query_selector_all("table tr")  # type: ignore[union-attr]
            for row in rows[1:]:
                tds = row.query_selector_all("td")
                if tds and len(tds) >= 2:
                    case_entry: dict[str, str] = {}
                    for i, td in enumerate(tds):
                        text = td.inner_text().strip()
                        if text:
                            case_entry[f"col_{i}"] = text
                    if case_entry:
                        cases.append(case_entry)
        except Exception:
            pass

        if not total_cases and cases:
            total_cases = len(cases)

        # Parse key-value lines for details
        for line in body_text.split("\n"):
            stripped = line.strip()
            if stripped and ":" in stripped:
                key, _, val = stripped.partition(":")
                if val.strip():
                    details[key.strip()] = val.strip()

        return TjspResult(
            queried_at=datetime.now(),
            search_term=search_term,
            total_cases=total_cases,
            cases=cases,
            details=details,
        )
