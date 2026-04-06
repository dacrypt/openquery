"""SBS source — Peru supervised financial entities lookup.

Queries Peru's Superintendencia de Banca, Seguros y AFP for supervised entity data.

Flow:
1. Navigate to the SBS information page
2. Enter entity name
3. Submit and parse result

Source: https://www.sbs.gob.pe/app/OTROS/infosistemafinanciero/paginas/BancaMultiple.aspx
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pe.sbs import SbsResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SBS_URL = "https://www.sbs.gob.pe/app/OTROS/infosistemafinanciero/paginas/BancaMultiple.aspx"


@register
class SbsSource(BaseSource):
    """Query Peru's SBS supervised financial entities."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pe.sbs",
            display_name="SBS — Superintendencia de Banca, Seguros y AFP",
            description="Peru supervised financial entities: banking, insurance, and AFP status",
            country="PE",
            url=SBS_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CUSTOM:
            raise SourceError("pe.sbs", f"Unsupported input type: {input.document_type}")

        name = input.extra.get("name", "").strip()
        if not name:
            raise SourceError("pe.sbs", "Must provide extra['name'] (entity name)")

        return self._query(name=name, audit=input.audit)

    def _query(self, name: str, audit: bool = False) -> SbsResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("pe.sbs", "nombre", name)

        with browser.page(SBS_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[id*="buscar"], input[name*="buscar"], '
                    'input[id*="entidad"], input[name*="entidad"], '
                    'input[placeholder*="entidad" i], input[type="text"]'
                )
                if search_input:
                    search_input.fill(name)
                    logger.info("Filled entity name: %s", name)

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

                result = self._parse_result(page, name)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("pe.sbs", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> SbsResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = SbsResult(queried_at=datetime.now(), search_term=search_term)
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
                    if "entidad" in label_lower or "nombre" in label_lower:
                        result.entity_name = value
                    elif "tipo" in label_lower:
                        result.entity_type = value
                    elif "estado" in label_lower:
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
                elif "estado" in lower and ":" in stripped and not result.status:
                    result.status = stripped.split(":", 1)[1].strip()

        return result
