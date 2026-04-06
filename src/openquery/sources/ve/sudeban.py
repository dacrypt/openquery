"""SUDEBAN source — Venezuela banking supervisor.

Queries the SUDEBAN (Superintendencia de las Instituciones del
Sector Bancario) for supervised banking institution data.

Source: https://www.sudeban.gob.ve/
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ve.sudeban import SudebanResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SUDEBAN_URL = "https://www.sudeban.gob.ve/"


@register
class SudebanSource(BaseSource):
    """Query SUDEBAN Venezuelan banking supervisor registry."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ve.sudeban",
            display_name="SUDEBAN — Sector Bancario",
            description="SUDEBAN Venezuelan banking supervisor: institution type, status, and authorization",  # noqa: E501
            country="VE",
            url=SUDEBAN_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (
            input.extra.get("entity_name", "")
            or input.extra.get("name", "")
            or input.document_number
        ).strip()
        if not search_term:
            raise SourceError("ve.sudeban", "Entity name required (pass via extra.entity_name or document_number)")  # noqa: E501
        return self._query(search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> SudebanResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("ve.sudeban", "entity", search_term)

        with browser.page(SUDEBAN_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(2000)

                search_input = page.locator(
                    'input[type="search"], input[placeholder*="buscar"], '
                    'input[placeholder*="Buscar"], input[type="text"]'
                ).first
                if search_input:
                    search_input.fill(search_term)
                    logger.info("Searching SUDEBAN for: %s", search_term)
                    search_input.press("Enter")
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
                raise SourceError("ve.sudeban", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> SudebanResult:
        body_text = page.inner_text("body")
        result = SudebanResult(queried_at=datetime.now(), search_term=search_term)

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if "institución" in lower and ":" in stripped and not result.entity_name:
                result.entity_name = stripped.split(":", 1)[1].strip()
            elif "tipo" in lower and ":" in stripped and not result.entity_type:
                result.entity_type = stripped.split(":", 1)[1].strip()
            elif "estado" in lower and ":" in stripped and not result.status:
                result.status = stripped.split(":", 1)[1].strip()

        return result
