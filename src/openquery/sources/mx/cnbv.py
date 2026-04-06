"""CNBV source — Mexico banking supervisor lookup.

Queries Mexico's CNBV for supervised financial entities by name.

Flow:
1. Navigate to the CNBV portal
2. Enter entity name
3. Submit and parse entity type and status

Source: https://www.cnbv.gob.mx/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.mx.cnbv import CnbvResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CNBV_URL = "https://www.cnbv.gob.mx/"


@register
class CnbvSource(BaseSource):
    """Query Mexico's CNBV supervised financial entities."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="mx.cnbv",
            display_name="CNBV — Comisión Nacional Bancaria y de Valores",
            description="Mexico banking supervisor: supervised entity type and status by name",
            country="MX",
            url=CNBV_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CUSTOM:
            raise SourceError("mx.cnbv", f"Unsupported input type: {input.document_type}")

        search_term = input.extra.get("entity", "").strip()
        if not search_term:
            raise SourceError("mx.cnbv", "Must provide extra['entity'] (entity name)")

        return self._query(search_term=search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> CnbvResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("mx.cnbv", "entidad", search_term)

        with browser.page(CNBV_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[id*="entidad"], input[name*="entidad"], '
                    'input[id*="search"], input[name*="search"], '
                    'input[placeholder*="entidad" i], input[type="search"], '
                    'input[type="text"]'
                )
                if search_input:
                    search_input.fill(search_term)
                    logger.info("Filled entity name: %s", search_term)

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
                raise SourceError("mx.cnbv", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> CnbvResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = CnbvResult(queried_at=datetime.now(), search_term=search_term)
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
                    if "entidad" in label_lower or "nombre" in label_lower or "raz" in label_lower:
                        result.entity_name = value
                    elif "tipo" in label_lower or "sector" in label_lower:
                        result.entity_type = value
                    elif "estado" in label_lower or "estatus" in label_lower or "condici" in label_lower:  # noqa: E501
                        result.status = value

        if details:
            result.details = details

        # Fallback: body text scan
        if not result.entity_name:
            for line in body_text.split("\n"):
                stripped = line.strip()
                lower = stripped.lower()
                if ("entidad" in lower or "nombre" in lower) and ":" in stripped:
                    result.entity_name = stripped.split(":", 1)[1].strip()
                elif "tipo" in lower and ":" in stripped and not result.entity_type:
                    result.entity_type = stripped.split(":", 1)[1].strip()
                elif ("estado" in lower or "estatus" in lower) and ":" in stripped and not result.status:  # noqa: E501
                    result.status = stripped.split(":", 1)[1].strip()

        return result
