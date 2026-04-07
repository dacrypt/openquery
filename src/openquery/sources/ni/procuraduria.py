"""Procuraduría source — Nicaragua anticorruption public records.

Queries the Procuraduría General de la República (PGR) of Nicaragua
for anticorruption and public records.

Source: https://www.pgr.gob.ni/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ni.procuraduria import NiProcuraduriaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

NI_PROCURADURIA_URL = "https://www.pgr.gob.ni/"


@register
class NiProcuraduriaSource(BaseSource):
    """Query Nicaragua Procuraduría anticorruption registry by name."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ni.procuraduria",
            display_name="PGR Nicaragua — Procuraduría Anticorrupción",
            description=(
                "Nicaragua Procuraduría: anticorruption and public records by name"
            ),
            country="NI",
            url=NI_PROCURADURIA_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("name", "") or input.document_number.strip()
        if not search_term:
            raise SourceError("ni.procuraduria", "Name is required")
        return self._query(search_term=search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> NiProcuraduriaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("ni.procuraduria", "name", search_term)

        with browser.page(NI_PROCURADURIA_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "page_loaded")

                search_input = page.query_selector(
                    'input[type="search"], input[type="text"], '
                    'input[name*="search"], input[name*="nombre"], '
                    'input[placeholder*="buscar"], input[id*="search"]'
                )
                if search_input:
                    search_input.fill(search_term)
                    logger.info("Querying NI Procuraduria for: %s", search_term)

                    submit_btn = page.query_selector(
                        'button[type="submit"], input[type="submit"], '
                        'button:has-text("Buscar"), button:has-text("Consultar")'
                    )
                    if submit_btn:
                        submit_btn.click()
                    else:
                        search_input.press("Enter")

                    page.wait_for_timeout(4000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_term)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("ni.procuraduria", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> NiProcuraduriaResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        lower_body = body_text.lower()

        found = any(
            kw in lower_body
            for kw in ["resultado", "encontrado", "registro", "expediente"]
        )

        record_type = ""
        status = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if any(kw in lower for kw in ["tipo", "clase"]) and ":" in stripped and not record_type:
                record_type = stripped.split(":", 1)[1].strip()
            elif "estado" in lower and ":" in stripped and not status:
                status = stripped.split(":", 1)[1].strip()

        return NiProcuraduriaResult(
            queried_at=datetime.now(),
            search_term=search_term,
            found=found,
            record_type=record_type,
            status=status,
            details=body_text.strip()[:500],
        )
