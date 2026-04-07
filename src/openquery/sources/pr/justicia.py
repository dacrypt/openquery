"""Justicia source — Puerto Rico Department of Justice registry.

Queries the PR Department of Justice for legal entity records.

Source: https://www.justicia.pr.gov/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pr.justicia import PrJusticiaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

JUSTICIA_URL = "https://www.justicia.pr.gov/"


@register
class PrJusticiaSource(BaseSource):
    """Query Puerto Rico Department of Justice registry by search term."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pr.justicia",
            display_name="Justicia PR — Registro de Entidades",
            description=(
                "Puerto Rico Department of Justice: legal entity registry by search term"
            ),
            country="PR",
            url=JUSTICIA_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("search_term", "") or input.document_number.strip()
        if not search_term:
            raise SourceError("pr.justicia", "Search term is required")
        return self._query(search_term=search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> PrJusticiaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("pr.justicia", "search_term", search_term)

        with browser.page(JUSTICIA_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "page_loaded")

                search_input = page.query_selector(
                    'input[type="search"], input[type="text"], '
                    'input[name*="search"], input[id*="search"], '
                    'input[name*="nombre"], input[placeholder*="buscar"]'
                )
                if search_input:
                    search_input.fill(search_term)
                    logger.info("Querying PR Justicia for: %s", search_term)

                    submit_btn = page.query_selector(
                        'button[type="submit"], input[type="submit"], '
                        'button:has-text("Buscar"), button:has-text("Search")'
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
                raise SourceError("pr.justicia", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> PrJusticiaResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        entity_name = ""
        entity_type = ""
        status = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if any(kw in lower for kw in ["entidad", "nombre", "entity"]) and ":" in stripped and not entity_name:  # noqa: E501
                entity_name = stripped.split(":", 1)[1].strip()
            elif any(kw in lower for kw in ["tipo", "type", "clase"]) and ":" in stripped and not entity_type:  # noqa: E501
                entity_type = stripped.split(":", 1)[1].strip()
            elif "estado" in lower and ":" in stripped and not status:
                status = stripped.split(":", 1)[1].strip()

        return PrJusticiaResult(
            queried_at=datetime.now(),
            search_term=search_term,
            entity_name=entity_name,
            entity_type=entity_type,
            status=status,
            details=body_text.strip()[:500],
        )
