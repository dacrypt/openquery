"""Uruguay BCU central bank supervised entities source.

Queries BCU (Banco Central del Uruguay) for supervised entity information
by entity name.

URL: https://www.bcu.gub.uy/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.uy.bcu import BcuResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

BCU_URL = "https://www.bcu.gub.uy/"


@register
class BcuSource(BaseSource):
    """Query Uruguay BCU central bank supervised entities."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="uy.bcu",
            display_name="BCU — Entidades Supervisadas (UY)",
            description="Uruguay BCU central bank: supervised entity status and type by entity name",
            country="UY",
            url=BCU_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("entity_name", "") or input.document_number
        if not search_term:
            raise SourceError("uy.bcu", "Entity name is required")
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> BcuResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("uy.bcu", "entity_name", search_term)

        with browser.page(BCU_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    "input[name*='entidad'], input[id*='entidad'], "
                    "input[name*='search'], input[name*='buscar'], input[type='text']"
                )
                if not search_input:
                    raise SourceError("uy.bcu", "Could not find search input field")

                search_input.fill(search_term)
                logger.info("Filled search term: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    "button[type='submit'], input[type='submit'], button[id*='buscar']"
                )
                if submit:
                    submit.click()
                else:
                    search_input.press("Enter")

                page.wait_for_timeout(3000)
                page.wait_for_selector(
                    "table, .resultado, .result, #resultado",
                    timeout=15000,
                )

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_term)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("uy.bcu", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> BcuResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = BcuResult(queried_at=datetime.now(), search_term=search_term)

        field_patterns = {
            "entidad": "entity_name",
            "denominacion": "entity_name",
            "tipo": "entity_type",
            "estado": "supervision_status",
            "supervision": "supervision_status",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_patterns.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value:
                        setattr(result, field, value)
                    break

        rows = page.query_selector_all("table tr")
        if len(rows) >= 2:
            cells = rows[1].query_selector_all("td")
            if cells:
                values = [(c.inner_text() or "").strip() for c in cells]
                if len(values) >= 1 and not result.entity_name:
                    result.entity_name = values[0]
                if len(values) >= 2 and not result.entity_type:
                    result.entity_type = values[1]
                if len(values) >= 3 and not result.supervision_status:
                    result.supervision_status = values[2]

        return result
