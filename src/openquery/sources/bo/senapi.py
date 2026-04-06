"""Bolivia SENAPI source — trademark and patent registry.

Queries Bolivia's SENAPI (Servicio Nacional de Propiedad Intelectual)
for trademark status, owner, and registration date.

Source: https://www.senapi.gob.bo/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.bo.senapi import SenapiResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SENAPI_URL = "https://www.senapi.gob.bo/"


@register
class SenapiSource(BaseSource):
    """Query Bolivia's SENAPI trademark and patent registry by trademark name."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="bo.senapi",
            display_name="SENAPI — Registro de Marcas y Patentes",
            description=(
                "Bolivia IP registry: trademark status, owner, and registration date"
                " (Servicio Nacional de Propiedad Intelectual)"
            ),
            country="BO",
            url=SENAPI_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (
            input.extra.get("trademark_name", "")
            or input.document_number
        )
        if not search_term:
            raise SourceError("bo.senapi", "trademark_name is required")
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> SenapiResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("bo.senapi", "trademark_name", search_term)

        with browser.page(SENAPI_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[name*="search"], input[name*="Search"], '
                    'input[id*="search"], input[placeholder*="marca"], '
                    'input[placeholder*="nombre"], input[type="search"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("bo.senapi", "Could not find search input field")

                search_input.fill(search_term)
                logger.info("Filled SENAPI search term: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'input[type="submit"], button[type="submit"], '
                    'button:has-text("Buscar"), button:has-text("Consultar"), '
                    'button:has-text("Search")'
                )
                if submit:
                    submit.click()
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
                raise SourceError("bo.senapi", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> SenapiResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = SenapiResult(queried_at=datetime.now(), search_term=search_term)

        trademark_name = ""
        owner = ""
        status = ""
        registration_date = ""
        details: dict[str, str] = {}

        # Try table rows first
        rows = page.query_selector_all("table tr")
        if rows:
            for row in rows[1:]:  # skip header
                cells = row.query_selector_all("td")
                if len(cells) >= 2:
                    texts = [c.inner_text().strip() for c in cells]
                    if not trademark_name and texts[0]:
                        trademark_name = texts[0]
                    if len(texts) > 1 and not owner:
                        owner = texts[1]
                    if len(texts) > 2 and not status:
                        status = texts[2]
                    if len(texts) > 3 and not registration_date:
                        registration_date = texts[3]
                    for i, text in enumerate(texts):
                        if text:
                            details[f"col_{i}"] = text

        # Fallback: parse text lines for labelled fields
        for line in body_text.split("\n"):
            stripped = line.strip()
            if not stripped or ":" not in stripped:
                continue
            key, _, val = stripped.partition(":")
            key_lower = key.strip().lower()
            val_clean = val.strip()
            if not val_clean:
                continue
            details[key.strip()] = val_clean
            if ("marca" in key_lower or "nombre" in key_lower) and not trademark_name:
                trademark_name = val_clean
            elif (
                "titular" in key_lower or "propietario" in key_lower or "dueño" in key_lower
            ) and not owner:
                owner = val_clean
            elif ("estado" in key_lower or "status" in key_lower) and not status:
                status = val_clean
            elif ("fecha" in key_lower or "registro" in key_lower) and not registration_date:
                registration_date = val_clean

        result.trademark_name = trademark_name
        result.owner = owner
        result.status = status
        result.registration_date = registration_date
        result.details = details
        return result
