"""RENIEC source — Peruvian national identity consultation.

Queries eldni.com (public RENIEC mirror) for DNI identity data.

Flow:
1. Navigate to eldni.com DNI search page
2. Enter DNI number
3. Submit search
4. Parse name fields from result
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pe.reniec import ReniecResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

RENIEC_URL = "https://eldni.com/pe/buscar-por-dni"


@register
class ReniecSource(BaseSource):
    """Query Peruvian national identity registry (RENIEC) via eldni.com."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pe.reniec",
            display_name="RENIEC — Consulta DNI",
            description="Peruvian national identity registry: full name and DNI status",
            country="PE",
            url=RENIEC_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        dni = input.document_number or input.extra.get("dni", "")
        if not dni:
            raise SourceError("pe.reniec", "Must provide document_number (DNI)")
        return self._query(dni=dni, audit=input.audit)

    def _query(self, dni: str, audit: bool = False) -> ReniecResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("pe.reniec", "cedula", dni)

        with browser.page(RENIEC_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(1500)

                dni_input = page.query_selector(
                    "input[name='dni'], input[id*='dni' i], input[placeholder*='DNI' i], "
                    "input[type='text']:first-of-type"
                )
                if dni_input:
                    dni_input.fill(dni)
                    logger.info("Filled DNI: %s", dni)
                else:
                    raise SourceError("pe.reniec", "DNI input field not found")

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    "button[type='submit'], input[type='submit'], "
                    "button:has-text('Buscar'), button:has-text('Consultar')"
                )
                if submit:
                    submit.click()
                else:
                    page.keyboard.press("Enter")

                page.wait_for_timeout(3000)
                page.wait_for_selector(
                    "table, .result, .resultado, #resultado, .card, [class*='result']",
                    timeout=15000,
                )

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, dni)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("pe.reniec", f"Query failed: {e}") from e

    def _parse_result(self, page, dni: str) -> ReniecResult:
        """Parse the eldni.com result page."""
        from datetime import datetime

        body_text = page.inner_text("body")
        result = ReniecResult(queried_at=datetime.now(), dni=dni)
        details: dict = {}

        # Try table rows (label/value pairs)
        rows = page.query_selector_all("table tr, .result tr, dl dt, dl dd")
        for row in rows:
            cells = row.query_selector_all("td, th")
            if len(cells) >= 2:
                label = (cells[0].inner_text() or "").strip().lower()
                value = (cells[1].inner_text() or "").strip()
                if value:
                    details[label] = value

        # Map common label patterns
        for label, value in details.items():
            if "nombre" in label and "apellido" not in label:
                result.nombre = value
            elif "paterno" in label:
                result.apellido_paterno = value
            elif "materno" in label:
                result.apellido_materno = value

        result.details = details

        # Fallback: regex on body text
        if not result.nombre:
            m = re.search(
                r"(?:Nombres?|Nombre\s+Propio)[:\s]+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ ]+)",
                body_text,
                re.IGNORECASE,
            )
            if m:
                result.nombre = m.group(1).strip()

        if not result.apellido_paterno:
            m = re.search(
                r"Apellido\s+Paterno[:\s]+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ ]+)",
                body_text,
                re.IGNORECASE,
            )
            if m:
                result.apellido_paterno = m.group(1).strip()

        if not result.apellido_materno:
            m = re.search(
                r"Apellido\s+Materno[:\s]+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ ]+)",
                body_text,
                re.IGNORECASE,
            )
            if m:
                result.apellido_materno = m.group(1).strip()

        return result
