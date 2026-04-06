"""Nicaragua INETER property/cadastro source.

Queries Nicaragua INETER (Instituto Nicaragüense de Estudios Territoriales) for cadastral data.
Browser-based, no CAPTCHA.

URL: https://www.ineter.gob.ni/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ni.ineter import NiIneterResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

INETER_URL = "https://www.ineter.gob.ni/"


@register
class NiIneterSource(BaseSource):
    """Query Nicaragua INETER cadastral property data."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ni.ineter",
            display_name="INETER — Catastro (NI)",
            description="Nicaragua INETER: cadastral property data by property code",
            country="NI",
            url=INETER_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_value = input.extra.get("property_code", "") or input.document_number
        if not search_value:
            raise SourceError("ni.ineter", "Property code is required")
        return self._query(search_value.strip(), audit=input.audit)

    def _query(self, search_value: str, audit: bool = False) -> NiIneterResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("ni.ineter", "property_code", search_value)

        with browser.page(INETER_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    "input[name*='catastro'], input[id*='catastro'], "
                    "input[name*='codigo'], input[name*='buscar'], input[type='text']"
                )
                if not search_input:
                    raise SourceError("ni.ineter", "Could not find search input field")

                search_input.fill(search_value)
                logger.info("Filled property code: %s", search_value)

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
                raise SourceError("ni.ineter", f"Query failed: {e}") from e

    def _parse_result(self, page, search_value: str) -> NiIneterResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = NiIneterResult(
            queried_at=datetime.now(),
            search_value=search_value,
        )

        field_patterns = {
            "codigo": "property_code",
            "propietario": "owner",
            "dueno": "owner",
            "dueño": "owner",
            "ubicacion": "location",
            "municipio": "location",
            "departamento": "location",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_patterns.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value and not getattr(result, field):
                        setattr(result, field, value)
                    break

        rows = page.query_selector_all("table tr")
        if len(rows) >= 2:
            cells = rows[1].query_selector_all("td")
            if cells:
                values = [(c.inner_text() or "").strip() for c in cells]
                if len(values) >= 1 and not result.property_code:
                    result.property_code = values[0]
                if len(values) >= 2 and not result.owner:
                    result.owner = values[1]
                if len(values) >= 3 and not result.location:
                    result.location = values[2]

        return result
