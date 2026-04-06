"""Registro Civil source — Ecuador civil registry lookup.

Queries Ecuador's Registro Civil for identity and civil status data by cedula.

Flow:
1. Navigate to the Registro Civil consultation page
2. Enter cedula number
3. Submit and parse result

Source: https://www.registrocivil.gob.ec/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ec.registro_civil import RegistroCivilEcResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

REGISTRO_CIVIL_EC_URL = "https://www.registrocivil.gob.ec/"


@register
class RegistroCivilEcSource(BaseSource):
    """Query Ecuador civil registry from Registro Civil."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ec.registro_civil",
            display_name="Registro Civil — Ecuador",
            description="Ecuador civil registry: identity data and civil status by cedula",
            country="EC",
            url=REGISTRO_CIVIL_EC_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        cedula = input.document_number or input.extra.get("cedula", "")
        if not cedula:
            raise SourceError("ec.registro_civil", "Must provide document_number (cedula)")
        return self._query(cedula=cedula, audit=input.audit)

    def _query(self, cedula: str, audit: bool = False) -> RegistroCivilEcResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("ec.registro_civil", "cedula", cedula)

        with browser.page(REGISTRO_CIVIL_EC_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                cedula_input = page.query_selector(
                    'input[id*="cedula"], input[name*="cedula"], '
                    'input[id*="identificacion"], input[name*="identificacion"], '
                    'input[placeholder*="cedula" i], input[type="text"]'
                )
                if cedula_input:
                    cedula_input.fill(cedula)
                    logger.info("Filled cedula: %s", cedula)
                else:
                    raise SourceError("ec.registro_civil", "Cedula input field not found")

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button:has-text("Consultar"), button:has-text("Buscar")'
                )
                if submit:
                    submit.click()
                else:
                    page.keyboard.press("Enter")

                page.wait_for_timeout(4000)
                page.wait_for_selector("body", timeout=15000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, cedula)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("ec.registro_civil", f"Query failed: {e}") from e

    def _parse_result(self, page, cedula: str) -> RegistroCivilEcResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = RegistroCivilEcResult(queried_at=datetime.now(), cedula=cedula)
        details: dict = {}

        rows = page.query_selector_all("table tr, .result tr, dl dt, dl dd")
        for row in rows:
            cells = row.query_selector_all("td, th")
            if len(cells) >= 2:
                label = (cells[0].inner_text() or "").strip()
                value = (cells[1].inner_text() or "").strip()
                if label and value:
                    details[label] = value
                    label_lower = label.lower()
                    if "nombre" in label_lower and not result.nombre:
                        result.nombre = value
                    elif "estado" in label_lower and "civil" in label_lower:
                        result.civil_status = value

        if details:
            result.details = details

        # Fallback: scan body text for key fields
        if not result.nombre:
            for line in body_text.split("\n"):
                stripped = line.strip()
                lower = stripped.lower()
                if "nombre" in lower and ":" in stripped:
                    result.nombre = stripped.split(":", 1)[1].strip()
                elif "estado civil" in lower and ":" in stripped:
                    result.civil_status = stripped.split(":", 1)[1].strip()

        return result
