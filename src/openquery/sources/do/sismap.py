"""SISMAP source — Dominican Republic government transparency.

Queries the Sistema de Monitoreo de la Administración Pública (SISMAP)
for government entity performance data.

Source: https://www.sismap.gob.do/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.do.sismap import SismapResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SISMAP_URL = "https://www.sismap.gob.do/"


@register
class SismapSource(BaseSource):
    """Query Dominican Republic SISMAP government performance by entity name."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="do.sismap",
            display_name="SISMAP — Transparencia Gubernamental",
            description=(
                "Dominican Republic SISMAP: government entity performance and transparency by entity name"  # noqa: E501
            ),
            country="DO",
            url=SISMAP_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("entity_name", "") or input.document_number.strip()
        if not search_term:
            raise SourceError("do.sismap", "Entity name is required")
        return self._query(search_term=search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> SismapResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("do.sismap", "entity_name", search_term)

        with browser.page(SISMAP_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "page_loaded")

                search_input = page.query_selector(
                    'input[name*="institucion"], input[id*="institucion"], '
                    'input[type="search"], input[type="text"], '
                    'input[name*="search"], input[placeholder*="institución"]'
                )
                if search_input:
                    search_input.fill(search_term)
                    logger.info("Querying SISMAP for entity: %s", search_term)

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
                raise SourceError("do.sismap", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> SismapResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        entity_name = ""
        performance_score = ""
        evaluation_period = ""
        status = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if any(kw in lower for kw in ["institución", "entidad", "nombre"]) and ":" in stripped and not entity_name:  # noqa: E501
                entity_name = stripped.split(":", 1)[1].strip()
            elif any(kw in lower for kw in ["puntuación", "índice", "calificación"]) and ":" in stripped and not performance_score:  # noqa: E501
                performance_score = stripped.split(":", 1)[1].strip()
            elif any(kw in lower for kw in ["período", "año", "evaluación"]) and ":" in stripped and not evaluation_period:  # noqa: E501
                evaluation_period = stripped.split(":", 1)[1].strip()
            elif "estado" in lower and ":" in stripped and not status:
                status = stripped.split(":", 1)[1].strip()

        return SismapResult(
            queried_at=datetime.now(),
            search_term=search_term,
            entity_name=entity_name,
            performance_score=performance_score,
            evaluation_period=evaluation_period,
            status=status,
            details=body_text.strip()[:500],
        )
