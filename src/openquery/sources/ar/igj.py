"""Argentina IGJ source — Inspección General de Justicia company registry.

Queries IGJ's public search for company registration details by name or correlative number.

Flow:
1. Navigate to IGJ search page
2. Enter company name or correlative number
3. Submit and parse company registration details
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ar.igj import IgjResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

IGJ_URL = "https://www2.jus.gov.ar/igj-vistas/Busqueda.aspx"


@register
class IgjSource(BaseSource):
    """Query Argentine IGJ company registry by name or correlative number."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ar.igj",
            display_name="IGJ — Inspección General de Justicia",
            description="Argentine company registry: registration status and tramite history",
            country="AR",
            url=IGJ_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (
            input.extra.get("company_name", "")
            or input.extra.get("correlative", "")
            or input.document_number
        )
        if not search_term:
            raise SourceError(
                "ar.igj",
                "Search term is required (extra.company_name or extra.correlative)",
            )
        return self._query(search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> IgjResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("ar.igj", "search", search_term)

        try:
            with browser.page(IGJ_URL, wait_until="networkidle") as page:
                if collector:
                    collector.attach(page)

                page.wait_for_timeout(2000)

                # Try to fill search input — IGJ uses various input selectors
                search_input = page.query_selector(
                    'input[name*="denominacion"], input[name*="search"], '
                    'input[id*="denominacion"], input[id*="search"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("ar.igj", "Could not find search input field")

                search_input.fill(search_term)
                logger.info("Searching IGJ for: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit form
                submit = page.query_selector(
                    'input[type="submit"], button[type="submit"], button.btn-primary'
                )
                if submit:
                    submit.click()
                else:
                    search_input.press("Enter")

                page.wait_for_timeout(3000)
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
            raise SourceError("ar.igj", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> IgjResult:
        from datetime import datetime

        result = IgjResult(queried_at=datetime.now(), search_term=search_term)
        body_text = page.inner_text("body")

        # Try table-based parsing first (most common IGJ result layout)
        rows = page.query_selector_all("table tr")
        details: dict[str, str] = {}
        for row in rows:
            cells = row.query_selector_all("td, th")
            if len(cells) >= 2:
                label = (cells[0].inner_text() or "").strip().lower()
                value = (cells[1].inner_text() or "").strip()
                details[label] = value
                if any(k in label for k in ("denominacion", "razon social", "nombre")):
                    result.company_name = result.company_name or value
                elif any(k in label for k in ("estado", "situacion", "status")):
                    result.registration_status = result.registration_status or value
                elif any(k in label for k in ("correlativo", "numero", "nro")):
                    result.correlative_number = result.correlative_number or value

        if details:
            result.details = details

        # Fallback: regex on body text
        import re

        if not result.company_name:
            m = re.search(
                r"(?:denominacion|razon\s*social)[:\s]+([^\n]+)", body_text, re.IGNORECASE
            )
            if m:
                result.company_name = m.group(1).strip()

        if not result.registration_status:
            m = re.search(r"(?:estado|situacion)[:\s]+([^\n]+)", body_text, re.IGNORECASE)
            if m:
                result.registration_status = m.group(1).strip()

        if not result.correlative_number:
            m = re.search(
                r"(?:correlativo|nro\.?\s*(?:de\s*)?registro)[:\s]+([^\n\s]+)",
                body_text,
                re.IGNORECASE,
            )
            if m:
                result.correlative_number = m.group(1).strip()

        return result
