"""Costa Rica property registry (Registro Inmobiliario) source.

Queries RNP Digital (Registro Nacional) for property title, liens,
and ownership by finca number.

URL: https://www.rnpdigital.com/registro_inmobiliario/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.cr.registro_inmobiliario import RegistroInmobiliarioResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

RNP_URL = "https://www.rnpdigital.com/registro_inmobiliario/"


@register
class RegistroInmobiliarioSource(BaseSource):
    """Query Costa Rica property registry (Registro Nacional / RNP Digital)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="cr.registro_inmobiliario",
            display_name="Registro Inmobiliario — RNP Digital (CR)",
            description="Costa Rica property registry: title, liens, and ownership by finca number",
            country="CR",
            url=RNP_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        finca_number = input.extra.get("finca_number", "") or input.document_number
        if not finca_number:
            raise SourceError("cr.registro_inmobiliario", "Finca number is required")
        return self._query(finca_number.strip(), audit=input.audit)

    def _query(self, finca_number: str, audit: bool = False) -> RegistroInmobiliarioResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("cr.registro_inmobiliario", "finca_number", finca_number)

        with browser.page(RNP_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                finca_input = page.query_selector(
                    "input[name*='finca'], input[id*='finca'], "
                    "input[name*='numero'], input[type='text']"
                )
                if not finca_input:
                    raise SourceError("cr.registro_inmobiliario", "Could not find finca number input field")

                finca_input.fill(finca_number)
                logger.info("Filled finca number: %s", finca_number)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    "button[type='submit'], input[type='submit'], button[id*='buscar'], button[id*='consultar']"
                )
                if submit:
                    submit.click()
                else:
                    finca_input.press("Enter")

                page.wait_for_timeout(3000)
                page.wait_for_selector(
                    "table, .resultado, .result, #resultado, .propiedad",
                    timeout=15000,
                )

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, finca_number)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("cr.registro_inmobiliario", f"Query failed: {e}") from e

    def _parse_result(self, page, finca_number: str) -> RegistroInmobiliarioResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = RegistroInmobiliarioResult(queried_at=datetime.now(), finca_number=finca_number)

        field_patterns = {
            "propietario": "owner",
            "titular": "owner",
            "dueno": "owner",
            "gravamen": "liens",
            "hipoteca": "liens",
            "tipo": "property_type",
            "naturaleza": "property_type",
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
                if len(values) >= 1 and not result.owner:
                    result.owner = values[0]
                if len(values) >= 2 and not result.liens:
                    result.liens = values[1]
                if len(values) >= 3 and not result.property_type:
                    result.property_type = values[2]

        return result
