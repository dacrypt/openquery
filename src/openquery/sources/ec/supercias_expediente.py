"""Supercias Expediente source — Ecuador corporate filings lookup.

Queries Ecuador's Superintendencia de Compañías for corporate filings by company name or RUC.

Flow:
1. Navigate to the Supercias portal
2. Enter company name or RUC
3. Submit and parse corporate filings

Source: https://www.supercias.gob.ec/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ec.supercias_expediente import SuperciasExpedienteResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SUPERCIAS_EXPEDIENTE_URL = "https://www.supercias.gob.ec/"


@register
class SuperciasExpedienteSource(BaseSource):
    """Query Ecuador's Supercias for corporate filings by company name or RUC."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ec.supercias_expediente",
            display_name="Supercias — Expediente Societario",
            description="Ecuador corporate filings: company case history and filings by name or RUC",  # noqa: E501
            country="EC",
            url=SUPERCIAS_EXPEDIENTE_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CUSTOM:
            raise SourceError(
                "ec.supercias_expediente",
                f"Unsupported input type: {input.document_type}",
            )

        search_term = input.extra.get("company", "").strip()
        if not search_term:
            raise SourceError(
                "ec.supercias_expediente",
                "Must provide extra['company'] (company name or RUC)",
            )

        return self._query(search_term=search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> SuperciasExpedienteResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("ec.supercias_expediente", "empresa", search_term)

        with browser.page(SUPERCIAS_EXPEDIENTE_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[id*="empresa"], input[name*="empresa"], '
                    'input[id*="ruc"], input[name*="ruc"], '
                    'input[placeholder*="empresa" i], input[type="search"], '
                    'input[type="text"]'
                )
                if search_input:
                    search_input.fill(search_term)
                    logger.info("Filled search term: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button:has-text("Buscar"), button:has-text("Consultar")'
                )
                if submit:
                    submit.click()
                else:
                    page.keyboard.press("Enter")

                page.wait_for_timeout(4000)
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
                raise SourceError("ec.supercias_expediente", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> SuperciasExpedienteResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = SuperciasExpedienteResult(queried_at=datetime.now(), search_term=search_term)
        details: dict = {}

        rows = page.query_selector_all("table tr, .result tr")
        for row in rows:
            cells = row.query_selector_all("td, th")
            if len(cells) >= 2:
                label = (cells[0].inner_text() or "").strip()
                value = (cells[1].inner_text() or "").strip()
                if label and value:
                    details[label] = value
                    label_lower = label.lower()
                    if "empresa" in label_lower or "raz" in label_lower or "nombre" in label_lower:
                        result.company_name = value
                    elif "ruc" in label_lower:
                        result.ruc = value
                    elif "expediente" in label_lower or "total" in label_lower or "tr" in label_lower:  # noqa: E501
                        result.total_filings = value

        if details:
            result.details = details

        # Fallback: body text scan
        if not result.company_name:
            for line in body_text.split("\n"):
                stripped = line.strip()
                lower = stripped.lower()
                if ("empresa" in lower or "raz" in lower or "nombre" in lower) and ":" in stripped:
                    result.company_name = stripped.split(":", 1)[1].strip()
                elif "ruc" in lower and ":" in stripped and not result.ruc:
                    result.ruc = stripped.split(":", 1)[1].strip()
                elif (
                    ("expediente" in lower or "total" in lower)
                    and ":" in stripped
                    and not result.total_filings
                ):
                    result.total_filings = stripped.split(":", 1)[1].strip()

        return result
