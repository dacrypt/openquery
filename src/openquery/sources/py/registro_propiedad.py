"""Registro Propiedad source — Paraguayan property registry.

Queries the Paraguay property registry (via Poder Judicial) for finca ownership data.

Flow:
1. Navigate to Paraguay property registry consultation page
2. Enter finca number
3. Parse result for owner, property type

Source: https://www.pj.gov.py/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.py.registro_propiedad import RegistroPropiedadPyResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

REGISTRO_PY_URL = "https://www.pj.gov.py/ebook/modules.php?name=registro_propiedad"


@register
class RegistroPropiedadPySource(BaseSource):
    """Query Paraguayan property registry."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="py.registro_propiedad",
            display_name="Registro de la Propiedad Paraguay",
            description="Paraguayan property registry — finca-based ownership data",
            country="PY",
            url=REGISTRO_PY_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        finca_number = input.extra.get("finca_number") or input.document_number
        if not finca_number:
            raise SourceError("py.registro_propiedad", "finca_number is required")
        return self._query(finca_number, audit=input.audit)

    def _query(self, finca_number: str, audit: bool = False) -> RegistroPropiedadPyResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("py.registro_propiedad", "custom", finca_number)

        with browser.page(REGISTRO_PY_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                finca_input = page.query_selector(
                    'input[type="text"], input[id*="finca"], '
                    'input[id*="numero"], input[id*="padron"]'
                )
                if not finca_input:
                    raise SourceError("py.registro_propiedad", "Could not find finca number input")

                finca_input.fill(finca_number)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="buscar"], button[id*="consultar"]'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    finca_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, finca_number)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("py.registro_propiedad", f"Query failed: {e}") from e

    def _parse_result(self, page, finca_number: str) -> RegistroPropiedadPyResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        owner = ""
        property_type = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if not stripped:
                continue
            if ("propietario" in lower or "titular" in lower or "nombre" in lower) and ":" in stripped:  # noqa: E501
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not owner:
                    owner = parts[1].strip()
            elif ("tipo" in lower or "clase" in lower or "inmueble" in lower) and ":" in stripped:
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not property_type:
                    property_type = parts[1].strip()

        return RegistroPropiedadPyResult(
            queried_at=datetime.now(),
            finca_number=finca_number,
            owner=owner,
            property_type=property_type,
            details={"queried": True},
        )
