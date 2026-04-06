"""Honduras RAP source — property registry (Registro de la Propiedad).

Queries Honduras' Instituto de la Propiedad (IP) portal for property ownership
data by property number.

Flow:
1. Navigate to https://www.ip.gob.hn/
2. Enter property number
3. Submit and parse owner, property type, and details

Source: https://www.ip.gob.hn/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.hn.rap import HnRapResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

RAP_URL = "https://www.ip.gob.hn/"


@register
class HnRapSource(BaseSource):
    """Query Honduras property registry (Registro de la Propiedad) by property number."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="hn.rap",
            display_name="RAP — Registro de la Propiedad Honduras",
            description=(
                "Honduras property registry: owner, property type, and registration details "
                "(Instituto de la Propiedad)"
            ),
            country="HN",
            url=RAP_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        property_number = input.extra.get("property_number", "") or input.document_number
        if not property_number:
            raise SourceError("hn.rap", "Property number is required")
        return self._query(property_number.strip(), audit=input.audit)

    def _query(self, property_number: str, audit: bool = False) -> HnRapResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("hn.rap", "property_number", property_number)

        with browser.page(RAP_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[id*="propiedad"], input[name*="propiedad"], '
                    'input[id*="folio"], input[name*="folio"], '
                    'input[id*="numero"], input[name*="numero"], '
                    'input[id*="search"], input[name*="search"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("hn.rap", "Could not find property number input field")

                search_input.fill(property_number)
                logger.info("Filled property number: %s", property_number)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="consultar"], button[id*="buscar"], '
                    'button:has-text("Consultar"), button:has-text("Buscar")'
                )
                if submit:
                    submit.click()
                else:
                    search_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, property_number)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("hn.rap", f"Query failed: {e}") from e

    def _parse_result(self, page, property_number: str) -> HnRapResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = HnRapResult(queried_at=datetime.now(), search_value=property_number)
        details: dict[str, str] = {}

        field_map = {
            "propietario": "owner",
            "dueño": "owner",
            "dueno": "owner",
            "titular": "owner",
            "tipo": "property_type",
            "clase": "property_type",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            lower = stripped.lower()
            for label, attr in field_map.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value:
                        setattr(result, attr, value)
                    break
            if ":" in stripped:
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip()
                if key and val:
                    details[key] = val

        result.details = details
        return result
