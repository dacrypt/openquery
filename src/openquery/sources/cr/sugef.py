"""SUGEF source — Costa Rica supervised financial entities lookup.

Queries Costa Rica's SUGEF (Superintendencia General de Entidades Financieras)
for supervised entity status and type by entity name.

Source: https://www.sugef.fi.cr/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.cr.sugef import SugefResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SUGEF_URL = "https://www.sugef.fi.cr/"


@register
class SugefSource(BaseSource):
    """Query Costa Rica SUGEF supervised financial entities by entity name."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="cr.sugef",
            display_name="SUGEF — Entidades Supervisadas",
            description=(
                "Costa Rica SUGEF: supervised financial entity status and type by entity name"
            ),
            country="CR",
            url=SUGEF_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (
            input.extra.get("entity_name", "") or input.document_number.strip()
        )
        if not search_term:
            raise SourceError("cr.sugef", "Entity name is required")
        return self._query(search_term=search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> SugefResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("cr.sugef", "search_term", search_term)

        with browser.page(SUGEF_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "page_loaded")

                search_input = page.query_selector(
                    'input[name*="entidad"], input[name*="search"], '
                    'input[id*="entidad"], input[id*="search"], '
                    'input[placeholder*="entidad"], input[placeholder*="nombre"], '
                    'input[type="search"], input[type="text"]'
                )
                if not search_input:
                    raise SourceError("cr.sugef", "Could not find search input field")

                search_input.fill(search_term)
                logger.info("Querying SUGEF for entity: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit_btn = page.query_selector(
                    'input[type="submit"], button[type="submit"], '
                    'button:has-text("Consultar"), button:has-text("Buscar"), '
                    'input[value*="Consultar"], input[value*="Buscar"]'
                )
                if submit_btn:
                    submit_btn.click()
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
                raise SourceError("cr.sugef", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> SugefResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        entity_name = ""
        entity_type = ""
        supervision_status = ""

        field_map = {
            "entidad": "entity_name",
            "nombre": "entity_name",
            "tipo": "entity_type",
            "clase": "entity_type",
            "estado": "supervision_status",
            "supervisión": "supervision_status",
            "supervisado": "supervision_status",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_map.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value:
                        if field == "entity_name" and not entity_name:
                            entity_name = value
                        elif field == "entity_type" and not entity_type:
                            entity_type = value
                        elif field == "supervision_status" and not supervision_status:
                            supervision_status = value
                    break

        return SugefResult(
            queried_at=datetime.now(),
            search_term=search_term,
            entity_name=entity_name,
            entity_type=entity_type,
            supervision_status=supervision_status,
            details=body_text.strip()[:500],
        )
