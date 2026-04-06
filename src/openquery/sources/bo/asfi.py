"""Bolivia ASFI source — supervised financial entities registry.

Queries Bolivia's ASFI (Autoridad de Supervisión del Sistema Financiero)
for supervised entity status, type, and license information.

Source: https://www.asfi.gob.bo/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.bo.asfi import AsfiResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

ASFI_URL = "https://www.asfi.gob.bo/"


@register
class AsfiSource(BaseSource):
    """Query Bolivia's ASFI supervised financial entities registry by entity name."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="bo.asfi",
            display_name="ASFI — Entidades Supervisadas",
            description=(
                "Bolivia financial regulator: supervised entity status, type, and license"
                " (Autoridad de Supervisión del Sistema Financiero)"
            ),
            country="BO",
            url=ASFI_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (
            input.extra.get("entity_name", "")
            or input.document_number
        )
        if not search_term:
            raise SourceError("bo.asfi", "entity_name is required")
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> AsfiResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("bo.asfi", "entity_name", search_term)

        with browser.page(ASFI_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[name*="search"], input[name*="Search"], '
                    'input[id*="search"], input[placeholder*="entidad"], '
                    'input[placeholder*="nombre"], input[type="search"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("bo.asfi", "Could not find search input field")

                search_input.fill(search_term)
                logger.info("Filled ASFI search term: %s", search_term)

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
                raise SourceError("bo.asfi", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> AsfiResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = AsfiResult(queried_at=datetime.now(), search_term=search_term)

        entity_name = ""
        entity_type = ""
        license_status = ""
        details: dict[str, str] = {}

        # Try table rows first
        rows = page.query_selector_all("table tr")
        if rows:
            for row in rows[1:]:  # skip header
                cells = row.query_selector_all("td")
                if len(cells) >= 2:
                    texts = [c.inner_text().strip() for c in cells]
                    if not entity_name and texts[0]:
                        entity_name = texts[0]
                    if len(texts) > 1 and not entity_type:
                        entity_type = texts[1]
                    if len(texts) > 2 and not license_status:
                        license_status = texts[2]
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
            if ("entidad" in key_lower or "nombre" in key_lower) and not entity_name:
                entity_name = val_clean
            elif "tipo" in key_lower and not entity_type:
                entity_type = val_clean
            elif (
                "licencia" in key_lower or "estado" in key_lower or "status" in key_lower
            ) and not license_status:
                license_status = val_clean

        result.entity_name = entity_name
        result.entity_type = entity_type
        result.license_status = license_status
        result.details = details
        return result
