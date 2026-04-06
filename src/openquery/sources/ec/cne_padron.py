"""CNE Padron source — Ecuador voter registration lookup.

Queries Ecuador's CNE (Consejo Nacional Electoral) for voter registration
and voting location by cedula and birth date.

Flow:
1. Navigate to the CNE consultation page
2. Enter cedula and birth date
3. Submit and parse result

Source: https://lugarvotacion.cne.gob.ec/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ec.cne_padron import CnePadronResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CNE_URL = "https://lugarvotacion.cne.gob.ec/"


@register
class CnePadronSource(BaseSource):
    """Query Ecuador voter registration from CNE."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ec.cne_padron",
            display_name="CNE — Padron Electoral",
            description="Ecuador voter registration and voting location from CNE",
            country="EC",
            url=CNE_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CEDULA:
            raise SourceError("ec.cne_padron", f"Only cedula supported, got: {input.document_type}")

        cedula = input.document_number.strip()
        if not cedula:
            raise SourceError("ec.cne_padron", "Cedula number is required")

        fecha_nacimiento = input.extra.get("fecha_nacimiento", "").strip()
        return self._query(cedula, fecha_nacimiento, audit=input.audit)

    def _query(
        self, cedula: str, fecha_nacimiento: str = "", audit: bool = False
    ) -> CnePadronResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("ec.cne_padron", "cedula", cedula)

        with browser.page(CNE_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_selector('input[type="text"]', timeout=15000)
                page.wait_for_timeout(2000)

                # Fill cedula
                cedula_input = page.query_selector(
                    'input[type="text"][id*="cedula"], '
                    'input[type="text"][id*="numero"], '
                    'input[type="text"][name*="cedula"], '
                    'input[type="text"][placeholder*="dula"], '
                    'input[type="text"]'
                )
                if not cedula_input:
                    raise SourceError("ec.cne_padron", "Could not find cedula input field")

                cedula_input.fill(cedula)

                # Fill birth date if provided
                if fecha_nacimiento:
                    date_input = page.query_selector(
                        'input[type="text"][id*="fecha"], '
                        'input[type="date"][id*="fecha"], '
                        'input[type="text"][name*="fecha"], '
                        'input[type="text"][placeholder*="fecha"]'
                    )
                    if date_input:
                        date_input.fill(fecha_nacimiento)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="consultar"], button[id*="buscar"], '
                    'a[id*="consultar"], button:has-text("Consultar"), '
                    'button:has-text("Buscar")'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    cedula_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, cedula)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("ec.cne_padron", f"Query failed: {e}") from e

    def _parse_result(self, page, cedula: str) -> CnePadronResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        nombre = ""
        provincia = ""
        canton = ""
        parroquia = ""
        recinto = ""
        direccion = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if "nombre" in lower and ":" in stripped:
                nombre = stripped.split(":", 1)[1].strip()
            elif "provincia" in lower and ":" in stripped:
                provincia = stripped.split(":", 1)[1].strip()
            elif ("canton" in lower or "cantón" in lower) and ":" in stripped:
                canton = stripped.split(":", 1)[1].strip()
            elif "parroquia" in lower and ":" in stripped:
                parroquia = stripped.split(":", 1)[1].strip()
            elif "recinto" in lower and ":" in stripped:
                recinto = stripped.split(":", 1)[1].strip()
            elif ("direcci" in lower or "ubicaci" in lower) and ":" in stripped:
                direccion = stripped.split(":", 1)[1].strip()

        return CnePadronResult(
            queried_at=datetime.now(),
            cedula=cedula,
            nombre=nombre,
            provincia=provincia,
            canton=canton,
            parroquia=parroquia,
            recinto=recinto,
            direccion=direccion,
        )
