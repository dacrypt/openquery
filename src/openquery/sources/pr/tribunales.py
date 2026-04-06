"""Poder Judicial SUMAC case lookup source — Puerto Rico.

Queries Puerto Rico's Poder Judicial SUMAC system for case status
and court filings.

Flow:
1. Navigate to https://poderjudicial.pr/consulta-de-casos/
2. Wait for search form to load
3. Fill party name, entity name, or case number
4. Submit and parse results
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pr.tribunales import TribunalesResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

TRIBUNALES_URL = "https://poderjudicial.pr/consulta-de-casos/"


@register
class TribunalesSource(BaseSource):
    """Query Puerto Rico's Poder Judicial SUMAC case lookup."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pr.tribunales",
            display_name="Poder Judicial PR — SUMAC",
            description=(
                "Puerto Rico Poder Judicial SUMAC: case status, documents filed, court"
            ),
            country="PR",
            url=TRIBUNALES_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query SUMAC for case data."""
        search_term = (
            input.extra.get("party_name", "")
            or input.extra.get("case_number", "")
            or input.extra.get("entity_name", "")
            or input.document_number
        )
        if not search_term:
            raise SourceError(
                "pr.tribunales", "party_name, case_number, or entity_name is required"
            )
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> TribunalesResult:
        """Full flow: launch browser, fill form, parse results."""
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("pr.tribunales", "search_term", search_term)

        with browser.page(TRIBUNALES_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Find search input
                search_input = page.query_selector(
                    'input[id*="case"], input[name*="case"], '
                    'input[id*="party"], input[name*="party"], '
                    'input[id*="nombre"], input[name*="nombre"], '
                    'input[id*="search"], input[name*="search"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("pr.tribunales", "Could not find search input field")

                search_input.fill(search_term)
                logger.info("Filled search term: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button:has-text("Buscar"), button:has-text("Search"), '
                    'button:has-text("Consultar")'
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
                raise SourceError("pr.tribunales", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> TribunalesResult:
        """Parse case data from the page DOM."""
        body_text = page.inner_text("body")
        result = TribunalesResult(search_term=search_term)
        details: dict[str, str] = {}
        parties: list[str] = []

        field_map = {
            "caso": "case_number",
            "case": "case_number",
            "número": "case_number",
            "numero": "case_number",
            "tribunal": "court",
            "court": "court",
            "sala": "court",
            "estado": "status",
            "status": "status",
            "estado del caso": "status",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            lower = stripped.lower()

            # Detect parties
            party_keywords = ("demandante", "demandado", "plaintiff", "defendant", "parte")
            if any(kw in lower for kw in party_keywords):
                if ":" in stripped:
                    val = stripped.split(":", 1)[1].strip()
                    if val:
                        parties.append(val)

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

        result.parties = parties
        result.details = details
        logger.info(
            "Tribunales result — case=%s, court=%s, status=%s, parties=%d",
            result.case_number, result.court, result.status, len(result.parties),
        )
        return result
