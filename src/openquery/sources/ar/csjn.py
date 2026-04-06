"""CSJN source — Argentine Supreme Court cases (Corte Suprema de Justicia de la Nación).

Queries the CSJN judicial portal for case status, rulings, and case numbers.

Flow:
1. Navigate to https://sj.csjn.gov.ar/sj/
2. Enter case number or party name
3. Parse case status and ruling information
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ar.csjn import CsjnResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CSJN_URL = "https://sj.csjn.gov.ar/sj/"


@register
class CsjnSource(BaseSource):
    """Query Argentine Supreme Court (CSJN) for case status and rulings."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ar.csjn",
            display_name="CSJN — Corte Suprema de Justicia de la Nación",
            description="Argentine Supreme Court case lookup: status, rulings, and case details",
            country="AR",
            url=CSJN_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (
            input.extra.get("case_number", "")
            or input.extra.get("party_name", "")
            or input.extra.get("expediente", "")
            or input.document_number
        )
        if not search_term:
            raise SourceError(
                "ar.csjn",
                "Case number or party name required (pass via extra.case_number,"
                " extra.party_name, or document_number)",
            )
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> CsjnResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("ar.csjn", "search_term", search_term)

        with browser.page(CSJN_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill search field
                search_input = page.query_selector(
                    'input[name*="expediente"], input[name*="causa"], '
                    'input[name*="buscar"], input[name*="parte"], '
                    'input[placeholder*="expediente"], input[type="text"]'
                )
                if not search_input:
                    raise SourceError("ar.csjn", "Could not find search field")
                search_input.fill(search_term)
                logger.info("Filled search: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    "button:has-text('Buscar'), button:has-text('Consultar'), "
                    "button:has-text('Buscar Causa')"
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
                raise SourceError("ar.csjn", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> CsjnResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = CsjnResult(queried_at=datetime.now(), search_term=search_term)

        # Case number
        m = re.search(r"(\d{1,6}[/\-]\d{4}(?:[/\-]\w+)?)", body_text)
        if m:
            result.case_number = m.group(1)

        # Court
        m = re.search(
            r"(?:tribunal|sala|juzgado|corte)[:\s]+([^\n\r|]{2,80})",
            body_text,
            re.IGNORECASE,
        )
        if m:
            result.court = m.group(1).strip()

        # Status
        m = re.search(
            r"(?:estado|estatus|situaci[oó]n)[:\s]+([^\n\r|]{2,60})",
            body_text,
            re.IGNORECASE,
        )
        if m:
            result.status = m.group(1).strip()

        # Ruling
        m = re.search(
            r"(?:sentencia|resoluci[oó]n|fallo|ruling)[:\s]+([^\n\r|]{2,120})",
            body_text,
            re.IGNORECASE,
        )
        if m:
            result.ruling = m.group(1).strip()

        result.details = {"raw_text": body_text[:500]}
        return result
