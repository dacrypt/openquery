"""SCJN/PJF source — Mexican federal judicial cases.

Queries the Poder Judicial de la Federación (PJF) / SCJN portal for
federal court cases by case number or party name.

Flow:
1. Navigate to https://www.serviciosenlinea.pjf.gob.mx/
2. Search by case number or party name
3. Parse case list with status, court, and parties
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.mx.scjn import MxCaseRecord, ScjnResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SCJN_URL = "https://www.serviciosenlinea.pjf.gob.mx/"


@register
class ScjnSource(BaseSource):
    """Query Mexico's PJF/SCJN portal for federal judicial cases."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="mx.scjn",
            display_name="SCJN/PJF — Expedientes Judiciales",
            description=(
                "Mexican federal judicial cases: status, resolutions, and sentencias"
                " from SCJN and federal courts"
            ),
            country="MX",
            url=SCJN_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (
            input.extra.get("case_number", "")
            or input.extra.get("party_name", "")
            or input.document_number
        )
        if not search_term:
            raise SourceError(
                "mx.scjn",
                "Search term required (pass via extra.case_number, extra.party_name,"
                " or document_number)",
            )
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> ScjnResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("mx.scjn", "search_term", search_term)

        with browser.page(SCJN_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill search field
                search_input = page.query_selector(
                    'input[name*="expediente"], input[name*="buscar"], '
                    'input[name*="search"], input[placeholder*="expediente"], '
                    'input[placeholder*="buscar"], input[type="text"]'
                )
                if not search_input:
                    raise SourceError("mx.scjn", "Could not find search field")
                search_input.fill(search_term)
                logger.info("Filled search term: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    "button:has-text('Buscar'), button:has-text('Consultar'), "
                    "button:has-text('Buscar Expediente')"
                )
                if submit:
                    submit.click()
                else:
                    search_input.press("Enter")

                page.wait_for_timeout(3000)
                page.wait_for_selector("body", timeout=15000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_term)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("mx.scjn", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> ScjnResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = ScjnResult(queried_at=datetime.now(), search_term=search_term)

        # Try to find structured rows (tables or list items)
        rows = page.query_selector_all("table tr, .expediente-item, .case-row, li.resultado")
        cases: list[MxCaseRecord] = []

        if rows:
            for row in rows:
                row_text = row.inner_text() if hasattr(row, "inner_text") else ""
                if not row_text.strip():
                    continue
                record = self._parse_case_row(row_text)
                if record.case_number or record.court or record.status:
                    cases.append(record)
        else:
            # Fallback: parse body text for case blocks
            cases = self._parse_body_text(body_text)

        result.cases = cases
        result.total = len(cases)

        # Override total if an explicit count is found
        m = re.search(
            r"(\d+)\s*(?:expediente|resultado|caso|registro)[s]?\s*(?:encontrado|hallado)?",
            body_text,
            re.IGNORECASE,
        )
        if m:
            try:
                result.total = int(m.group(1))
            except ValueError:
                pass

        return result

    def _parse_case_row(self, row_text: str) -> MxCaseRecord:
        """Extract case fields from a single table row or list item text."""
        record = MxCaseRecord()

        m = re.search(r"(\d{1,5}/\d{4}(?:-\d+)?)", row_text)
        if m:
            record.case_number = m.group(1)

        m = re.search(
            r"(?:juzgado|tribunal|sala|circuito)[:\s]+([^\n\r|]+)",
            row_text,
            re.IGNORECASE,
        )
        if m:
            record.court = m.group(1).strip()

        m = re.search(
            r"(?:tipo|materia|clase)[:\s]+([^\n\r|]+)",
            row_text,
            re.IGNORECASE,
        )
        if m:
            record.case_type = m.group(1).strip()

        m = re.search(
            r"(?:estado|estatus|situaci[oó]n)[:\s]+([^\n\r|]+)",
            row_text,
            re.IGNORECASE,
        )
        if m:
            record.status = m.group(1).strip()

        m = re.search(
            r"(?:parte|actor|demandado|quejoso)[:\s]+([^\n\r|]+)",
            row_text,
            re.IGNORECASE,
        )
        if m:
            record.parties = m.group(1).strip()

        m = re.search(
            r"(?:fecha)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})",
            row_text,
            re.IGNORECASE,
        )
        if m:
            record.date = m.group(1).strip()

        return record

    def _parse_body_text(self, body_text: str) -> list[MxCaseRecord]:
        """Fallback parser: scan full body text for case number patterns."""
        cases: list[MxCaseRecord] = []
        seen: set[str] = set()

        for m in re.finditer(r"(\d{1,5}/\d{4}(?:-\d+)?)", body_text):
            case_number = m.group(1)
            if case_number in seen:
                continue
            seen.add(case_number)

            # Extract context around the case number
            start = max(0, m.start() - 50)
            end = min(len(body_text), m.end() + 200)
            context = body_text[start:end]

            record = self._parse_case_row(context)
            record.case_number = case_number
            cases.append(record)

        return cases
