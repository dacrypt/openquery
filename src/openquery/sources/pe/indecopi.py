"""INDECOPI source — Peruvian trademark and patent search.

Queries INDECOPI for trademark/patent status, owner, and registration details.

Flow:
1. Navigate to INDECOPI trademark consultation page
2. Enter trademark name or registration number
3. Submit search
4. Parse result table
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pe.indecopi import IndecopiResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

INDECOPI_URL = "https://sistramite.indecopi.gob.pe/consultaMarcas/consultaMarcas.aspx"


@register
class IndecopiSource(BaseSource):
    """Query Peruvian trademark and patent registry (INDECOPI)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pe.indecopi",
            display_name="INDECOPI — Consulta de Marcas",
            description=(
                "Peruvian trademark and patent registry: status, owner, classes, registration date"
            ),
            country="PE",
            url=INDECOPI_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("search_term", "") or input.document_number or ""
        if not search_term:
            raise SourceError(
                "pe.indecopi",
                "Must provide extra.search_term or document_number "
                "(trademark name or registration number)",
            )
        return self._query(search_term=search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> IndecopiResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("pe.indecopi", "custom", search_term)

        with browser.page(INDECOPI_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    "input[name*='marca' i], input[id*='marca' i], "
                    "input[name*='search' i], input[id*='search' i], "
                    "input[placeholder*='marca' i], input[placeholder*='nombre' i], "
                    "input[type='text']"
                )
                if search_input:
                    search_input.fill(search_term)
                    logger.info("Filled search term: %s", search_term)
                else:
                    raise SourceError("pe.indecopi", "Search input field not found")

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    "button[type='submit'], input[type='submit'], "
                    "button:has-text('Buscar'), button:has-text('Consultar'), "
                    "input[value='Buscar']"
                )
                if submit:
                    submit.click()
                else:
                    page.keyboard.press("Enter")

                page.wait_for_timeout(3000)
                page.wait_for_selector(
                    "table, .resultado, #resultado, .list-group, .GridView",
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
                raise SourceError("pe.indecopi", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> IndecopiResult:
        """Parse the INDECOPI trademark result page."""
        from datetime import datetime

        body_text = page.inner_text("body")
        result = IndecopiResult(queried_at=datetime.now(), search_term=search_term)
        details: dict = {}

        # Parse table rows
        rows = page.query_selector_all("table tbody tr, table tr")
        for row in rows:
            cells = row.query_selector_all("td")
            if not cells or len(cells) < 2:
                continue
            values = [(c.inner_text() or "").strip() for c in cells]
            # First result row: marca, titular, estado, fecha, clases
            if not result.trademark_name and values[0]:
                result.trademark_name = values[0]
                if len(values) > 1:
                    result.owner = values[1]
                if len(values) > 2:
                    result.status = values[2]
                if len(values) > 3:
                    result.registration_date = values[3]
                if len(values) > 4:
                    classes_raw = values[4]
                    result.classes = [
                        c.strip() for c in re.split(r"[,;/\s]+", classes_raw) if c.strip()
                    ]

        # Label/value table variant
        for row in rows:
            cells = row.query_selector_all("td")
            if len(cells) == 2:
                label = (cells[0].inner_text() or "").strip().lower()
                value = (cells[1].inner_text() or "").strip()
                if value:
                    details[label] = value

        result.details = details

        # Fallback regex
        if not result.trademark_name:
            m = re.search(
                r"(?:Marca|Signo)[:\s]+([^\n]+)", body_text, re.IGNORECASE
            )
            if m:
                result.trademark_name = m.group(1).strip()

        if not result.owner:
            m = re.search(
                r"(?:Titular|Propietario|Due[ñn]o)[:\s]+([^\n]+)",
                body_text, re.IGNORECASE,
            )
            if m:
                result.owner = m.group(1).strip()

        if not result.status:
            m = re.search(
                r"(?:Estado|Situaci[oó]n)[:\s]+([^\n]+)", body_text, re.IGNORECASE
            )
            if m:
                result.status = m.group(1).strip()

        if not result.registration_date:
            m = re.search(
                r"(?:Fecha\s+de\s+Registro|Fecha\s+Inscripci[oó]n)[:\s]+([^\n]+)",
                body_text, re.IGNORECASE,
            )
            if m:
                result.registration_date = m.group(1).strip()

        return result
