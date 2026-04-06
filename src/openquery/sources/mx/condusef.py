"""CONDUSEF source — Mexican financial institution complaints (Buró de Entidades Financieras).

Queries the CONDUSEF Buró portal for complaint counts and resolution rates
for a given financial institution.

Flow:
1. Navigate to https://www.buro.gob.mx/
2. Search by institution name
3. Parse complaint statistics
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.mx.condusef import CondusefResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CONDUSEF_URL = "https://www.buro.gob.mx/"


@register
class CondusefSource(BaseSource):
    """Query Mexican CONDUSEF Buró de Entidades Financieras for institution complaints."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="mx.condusef",
            display_name="CONDUSEF — Buró de Entidades Financieras",
            description="Mexican CONDUSEF financial institution complaints: counts and resolution rates",  # noqa: E501
            country="MX",
            url=CONDUSEF_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        institution = input.extra.get("institution_name", "") or input.document_number
        if not institution:
            raise SourceError(
                "mx.condusef",
                "Institution name is required (pass via extra.institution_name or document_number)",
            )
        return self._query(institution.strip(), audit=input.audit)

    def _query(self, institution: str, audit: bool = False) -> CondusefResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("mx.condusef", "institution_name", institution)

        with browser.page(CONDUSEF_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill institution search field
                search_input = page.query_selector(
                    'input[name*="entidad"], input[name*="institucion"], '
                    'input[placeholder*="entidad"], input[placeholder*="busca"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("mx.condusef", "Could not find institution search field")
                search_input.fill(institution)
                logger.info("Filled institution: %s", institution)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    "button:has-text('Buscar'), button:has-text('Consultar')"
                )
                if submit:
                    submit.click()
                else:
                    search_input.press("Enter")

                page.wait_for_timeout(3000)
                page.wait_for_selector("body", timeout=15000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, institution)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("mx.condusef", f"Query failed: {e}") from e

    def _parse_result(self, page, institution: str) -> CondusefResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        result = CondusefResult(queried_at=datetime.now(), institution_name=institution)

        # Extract total complaints
        m = re.search(
            r"(?:queja|reclamaci[oó]n|complaint)[s\w]*[:\s]+(\d[\d,\.]*)"
            r"|(\d[\d,\.]*)\s*(?:queja|reclamaci[oó]n|complaint)",
            body_text,
            re.IGNORECASE,
        )
        if m:
            raw = (m.group(1) or m.group(2) or "").replace(",", "").replace(".", "")
            try:
                result.total_complaints = int(raw)
            except ValueError:
                pass

        # Extract resolution rate
        m = re.search(
            r"(\d{1,3}(?:[.,]\d+)?)\s*%\s*(?:resoluci[oó]n|resuelto|favorable)",
            body_text,
            re.IGNORECASE,
        )
        if not m:
            m = re.search(
                r"(?:resoluci[oó]n|resuelto)[:\s]+(\d{1,3}(?:[.,]\d+)?)\s*%",
                body_text,
                re.IGNORECASE,
            )
        if m:
            result.resolution_rate = f"{m.group(1)}%"

        # Extract product names from list items or table cells
        products: list[str] = []
        rows = page.query_selector_all("table tr, li.producto, .producto")
        for row in rows:
            text = (row.inner_text() or "").strip()
            if text and len(text) < 100:
                products.append(text)
        result.products = products[:10]  # cap at 10

        result.details = body_text[:500].strip()
        return result
