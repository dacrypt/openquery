"""MINFIN source — Guatemala ministry of finance budget data.

Queries the Ministerio de Finanzas Públicas (MINFIN) for entity budget data.

Source: https://www.minfin.gob.gt/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.gt.minfin import MinfinResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

MINFIN_URL = "https://www.minfin.gob.gt/"


@register
class MinfinSource(BaseSource):
    """Query Guatemala MINFIN budget data by entity name."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="gt.minfin",
            display_name="MINFIN — Datos Presupuestarios",
            description=(
                "Guatemala MINFIN: tax and budget data by entity name"
            ),
            country="GT",
            url=MINFIN_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("entity_name", "") or input.document_number.strip()
        if not search_term:
            raise SourceError("gt.minfin", "Entity name is required")
        return self._query(search_term=search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> MinfinResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("gt.minfin", "entity_name", search_term)

        with browser.page(MINFIN_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "page_loaded")

                search_input = page.query_selector(
                    'input[name*="entidad"], input[id*="entidad"], '
                    'input[type="search"], input[type="text"], '
                    'input[name*="search"], input[placeholder*="entidad"]'
                )
                if search_input:
                    search_input.fill(search_term)
                    logger.info("Querying MINFIN for entity: %s", search_term)

                    submit_btn = page.query_selector(
                        'button[type="submit"], input[type="submit"], '
                        'button:has-text("Consultar"), button:has-text("Buscar")'
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
                raise SourceError("gt.minfin", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> MinfinResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        entity_name = ""
        budget_amount = ""
        fiscal_year = ""
        status = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if any(kw in lower for kw in ["entidad", "nombre", "unidad"]) and ":" in stripped and not entity_name:  # noqa: E501
                entity_name = stripped.split(":", 1)[1].strip()
            elif any(kw in lower for kw in ["presupuesto", "monto", "asignación"]) and ":" in stripped and not budget_amount:  # noqa: E501
                budget_amount = stripped.split(":", 1)[1].strip()
            elif any(kw in lower for kw in ["año", "ejercicio", "período"]) and ":" in stripped and not fiscal_year:  # noqa: E501
                fiscal_year = stripped.split(":", 1)[1].strip()
            elif "estado" in lower and ":" in stripped and not status:
                status = stripped.split(":", 1)[1].strip()

        return MinfinResult(
            queried_at=datetime.now(),
            search_term=search_term,
            entity_name=entity_name,
            budget_amount=budget_amount,
            fiscal_year=fiscal_year,
            status=status,
            details=body_text.strip()[:500],
        )
