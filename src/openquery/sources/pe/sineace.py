"""SINEACE source — Peru educational accreditation lookup.

Queries Peru's SINEACE for educational institution accreditation status by name.

Flow:
1. Navigate to the SINEACE portal
2. Enter institution name
3. Submit and parse accreditation status

Source: https://www.sineace.gob.pe/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pe.sineace import SineaceResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SINEACE_URL = "https://www.sineace.gob.pe/"


@register
class SineaceSource(BaseSource):
    """Query Peru's SINEACE educational accreditation by institution name."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pe.sineace",
            display_name="SINEACE — Sistema Nacional de Evaluación, Acreditación y Certificación de la Calidad Educativa",  # noqa: E501
            description="Peru educational accreditation: institution accreditation status by name",
            country="PE",
            url=SINEACE_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CUSTOM:
            raise SourceError("pe.sineace", f"Unsupported input type: {input.document_type}")

        search_term = input.extra.get("institution", "").strip()
        if not search_term:
            raise SourceError("pe.sineace", "Must provide extra['institution'] (institution name)")

        return self._query(search_term=search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> SineaceResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("pe.sineace", "institucion", search_term)

        with browser.page(SINEACE_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[id*="institu"], input[name*="institu"], '
                    'input[placeholder*="institu" i], input[type="search"], '
                    'input[type="text"]'
                )
                if search_input:
                    search_input.fill(search_term)
                    logger.info("Filled institution name: %s", search_term)

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
                raise SourceError("pe.sineace", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> SineaceResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = SineaceResult(queried_at=datetime.now(), search_term=search_term)
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
                    if "instituci" in label_lower or "nombre" in label_lower:
                        result.institution_name = value
                    elif "acreditaci" in label_lower or "estado" in label_lower or "condici" in label_lower:  # noqa: E501
                        result.accreditation_status = value

        if details:
            result.details = details

        # Fallback: body text scan
        if not result.institution_name:
            for line in body_text.split("\n"):
                stripped = line.strip()
                lower = stripped.lower()
                if ("instituci" in lower or "nombre" in lower) and ":" in stripped:
                    result.institution_name = stripped.split(":", 1)[1].strip()
                elif (
                    ("acreditaci" in lower or "estado" in lower)
                    and ":" in stripped
                    and not result.accreditation_status
                ):
                    result.accreditation_status = stripped.split(":", 1)[1].strip()

        return result
