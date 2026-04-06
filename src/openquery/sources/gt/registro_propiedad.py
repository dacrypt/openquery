"""Guatemala property registry source.

Queries Guatemala property registry (eRegistros / Registro Mercantil).
Browser-based, no CAPTCHA, no auth.

URL: https://eregistros.registromercantil.gob.gt/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.gt.registro_propiedad import GtRegistroPropiedadResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

REGISTRO_PROPIEDAD_URL = "https://eregistros.registromercantil.gob.gt/"


@register
class GtRegistroPropiedadSource(BaseSource):
    """Query Guatemala property registry (eRegistros)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="gt.registro_propiedad",
            display_name="Registro de la Propiedad (GT)",
            description="Guatemala property registry: finca owner, property type, and details by finca number",  # noqa: E501
            country="GT",
            url=REGISTRO_PROPIEDAD_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_value = input.extra.get("finca_number", "") or input.document_number
        if not search_value:
            raise SourceError("gt.registro_propiedad", "Finca number is required")
        return self._query(search_value.strip(), audit=input.audit)

    def _query(self, search_value: str, audit: bool = False) -> GtRegistroPropiedadResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("gt.registro_propiedad", "finca_number", search_value)

        with browser.page(REGISTRO_PROPIEDAD_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    "input[name*='finca'], input[id*='finca'], "
                    "input[name*='search'], input[name*='buscar'], input[type='text']"
                )
                if not search_input:
                    raise SourceError("gt.registro_propiedad", "Could not find search input field")

                search_input.fill(search_value)
                logger.info("Filled finca number: %s", search_value)

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
                raise SourceError("gt.registro_propiedad", f"Query failed: {e}") from e

    def _parse_result(self, page, search_value: str) -> GtRegistroPropiedadResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = GtRegistroPropiedadResult(
            queried_at=datetime.now(),
            search_value=search_value,
        )

        field_patterns = {
            "finca": "finca_number",
            "propietario": "owner",
            "dueno": "owner",
            "dueño": "owner",
            "tipo": "property_type",
        }

        details: dict = {}
        for line in body_text.split("\n"):
            stripped = line.strip()
            if not stripped or ":" not in stripped:
                continue
            lower = stripped.lower()
            key, _, value = stripped.partition(":")
            value = value.strip()
            if not value:
                continue
            matched = False
            for label, field in field_patterns.items():
                if label in lower:
                    if not getattr(result, field):
                        setattr(result, field, value)
                    matched = True
                    break
            if not matched:
                details[key.strip()] = value

        result.details = details

        rows = page.query_selector_all("table tr")
        if len(rows) >= 2:
            cells = rows[1].query_selector_all("td")
            if cells:
                values = [(c.inner_text() or "").strip() for c in cells]
                if len(values) >= 1 and not result.finca_number:
                    result.finca_number = values[0]
                if len(values) >= 2 and not result.owner:
                    result.owner = values[1]
                if len(values) >= 3 and not result.property_type:
                    result.property_type = values[2]

        return result
