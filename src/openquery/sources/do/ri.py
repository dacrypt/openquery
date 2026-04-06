"""Dominican Republic Registro Inmobiliario property registry source.

Queries the Registro Inmobiliario for property status and ownership
by cadastral designation.

URL: https://servicios.ri.gob.do/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.do.ri import RiResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

RI_URL = "https://servicios.ri.gob.do/"


@register
class RiSource(BaseSource):
    """Query Dominican Republic Registro Inmobiliario property registry."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="do.ri",
            display_name="Registro Inmobiliario (RD)",
            description="Dominican Republic property registry: status and ownership by cadastral designation",
            country="DO",
            url=RI_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_value = input.extra.get("cadastral", "") or input.document_number
        if not search_value:
            raise SourceError("do.ri", "Cadastral designation is required")
        return self._query(search_value.strip(), audit=input.audit)

    def _query(self, search_value: str, audit: bool = False) -> RiResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("do.ri", "cadastral", search_value)

        with browser.page(RI_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    "input[name*='designacion'], input[id*='designacion'], "
                    "input[name*='catastral'], input[type='text']"
                )
                if not search_input:
                    raise SourceError("do.ri", "Could not find search input field")

                search_input.fill(search_value)
                logger.info("Filled search value: %s", search_value)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    "button[type='submit'], input[type='submit'], button[id*='buscar']"
                )
                if submit:
                    submit.click()
                else:
                    search_input.press("Enter")

                page.wait_for_timeout(3000)
                page.wait_for_selector(
                    "table, .resultado, .result, #resultado",
                    timeout=15000,
                )

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_value)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("do.ri", f"Query failed: {e}") from e

    def _parse_result(self, page, search_value: str) -> RiResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = RiResult(queried_at=datetime.now(), search_value=search_value)

        field_patterns = {
            "estado": "property_status",
            "propietario": "owner",
            "dueno": "owner",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_patterns.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value:
                        setattr(result, field, value)
                    break

        rows = page.query_selector_all("table tr")
        if len(rows) >= 2:
            cells = rows[1].query_selector_all("td")
            if cells:
                values = [(c.inner_text() or "").strip() for c in cells]
                if len(values) >= 1 and not result.property_status:
                    result.property_status = values[0]
                if len(values) >= 2 and not result.owner:
                    result.owner = values[1]

        return result
