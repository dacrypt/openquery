"""IMPI source — Mexico trademark/patent search (Instituto Mexicano de la Propiedad Industrial).

Queries IMPI's Marcanet portal for trademark status, owner, and class.

Flow:
1. Navigate to https://marcanet.impi.gob.mx/
2. Enter trademark name
3. Parse status, owner, class, and registration date
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.mx.impi import ImpiResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

IMPI_URL = "https://marcanet.impi.gob.mx/"


@register
class ImpiSource(BaseSource):
    """Query IMPI's Marcanet portal for trademark/patent search."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="mx.impi",
            display_name="IMPI Marcanet — Búsqueda de Marcas",
            description="Mexico trademark search: status, owner, and class from IMPI Marcanet portal",  # noqa: E501
            country="MX",
            url=IMPI_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (
            input.extra.get("trademark_name", "")
            or input.extra.get("marca", "")
            or input.document_number
        )
        if not search_term:
            raise SourceError(
                "mx.impi",
                "Trademark name required (pass via extra.trademark_name or document_number)",
            )
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> ImpiResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("mx.impi", "trademark_name", search_term)

        with browser.page(IMPI_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill trademark search field
                search_input = page.query_selector(
                    'input[name*="marca"], input[name*="denominacion"], '
                    'input[name*="buscar"], input[name*="search"], '
                    'input[placeholder*="marca"], input[type="text"]'
                )
                if not search_input:
                    raise SourceError("mx.impi", "Could not find trademark search field")
                search_input.fill(search_term)
                logger.info("Filled trademark search: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    "button:has-text('Buscar'), button:has-text('Consultar'), "
                    "button:has-text('Search')"
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
                raise SourceError("mx.impi", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> ImpiResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = ImpiResult(queried_at=datetime.now(), search_term=search_term)

        # Try to get trademark name from result
        m = re.search(
            r"(?:denominaci[oó]n|marca|trademark)[:\s]+([^\n\r|]{2,80})",
            body_text,
            re.IGNORECASE,
        )
        if m:
            result.trademark_name = m.group(1).strip()

        # Owner
        m = re.search(
            r"(?:titular|propietario|owner)[:\s]+([^\n\r|]{2,80})",
            body_text,
            re.IGNORECASE,
        )
        if m:
            result.owner = m.group(1).strip()

        # Status
        m = re.search(
            r"(?:estado|status|estatus)[:\s]+([^\n\r|]{2,50})",
            body_text,
            re.IGNORECASE,
        )
        if m:
            result.status = m.group(1).strip()

        # Registration date
        m = re.search(
            r"(?:fecha|registro|registration)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})",
            body_text,
            re.IGNORECASE,
        )
        if m:
            result.registration_date = m.group(1).strip()

        # Class
        m = re.search(
            r"(?:clase|class)[:\s]+(\d{1,2}[^\n\r|]{0,40})",
            body_text,
            re.IGNORECASE,
        )
        if m:
            result.trademark_class = m.group(1).strip()

        result.details = {"raw_text": body_text[:500]}
        return result
