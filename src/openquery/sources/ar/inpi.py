"""INPI source — Argentine trademark search (Instituto Nacional de la Propiedad Industrial).

Queries INPI's portal for trademark status, owner, and class.

Flow:
1. Navigate to https://portaltramites.inpi.gob.ar/marcas_702_702busq.php
2. Enter trademark name
3. Parse status, owner, and class
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ar.inpi import InpiResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

INPI_URL = "https://portaltramites.inpi.gob.ar/marcas_702_702busq.php"


@register
class InpiSource(BaseSource):
    """Query Argentine INPI portal for trademark search."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ar.inpi",
            display_name="INPI — Búsqueda de Marcas",
            description="Argentine trademark search: status and owner from INPI portal",
            country="AR",
            url=INPI_URL,
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
                "ar.inpi",
                "Trademark name required (pass via extra.trademark_name or document_number)",
            )
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> InpiResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("ar.inpi", "trademark_name", search_term)

        with browser.page(INPI_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill trademark search field
                search_input = page.query_selector(
                    'input[name*="denominacion"], input[name*="marca"], '
                    'input[name*="buscar"], input[name*="search"], '
                    'input[placeholder*="marca"], input[type="text"]'
                )
                if not search_input:
                    raise SourceError("ar.inpi", "Could not find trademark search field")
                search_input.fill(search_term)
                logger.info("Filled trademark search: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    "button:has-text('Buscar'), button:has-text('Consultar'), "
                    "input[value='Buscar']"
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
                raise SourceError("ar.inpi", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> InpiResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = InpiResult(queried_at=datetime.now(), search_term=search_term)

        # Trademark name from results
        m = re.search(
            r"(?:denominaci[oó]n|marca)[:\s]+([^\n\r|]{2,80})",
            body_text,
            re.IGNORECASE,
        )
        if m:
            result.trademark_name = m.group(1).strip()

        # Owner
        m = re.search(
            r"(?:titular|propietario)[:\s]+([^\n\r|]{2,80})",
            body_text,
            re.IGNORECASE,
        )
        if m:
            result.owner = m.group(1).strip()

        # Status
        m = re.search(
            r"(?:estado|estatus)[:\s]+([^\n\r|]{2,50})",
            body_text,
            re.IGNORECASE,
        )
        if m:
            result.status = m.group(1).strip()

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
