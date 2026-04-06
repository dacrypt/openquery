"""JNE source — Peru electoral registry lookup.

Queries Peru's Jurado Nacional de Elecciones for voter registration data by DNI.

Flow:
1. Navigate to the JNE portal
2. Enter DNI number
3. Submit and parse result

Source: https://portal.jne.gob.pe/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pe.jne import JneResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

JNE_URL = "https://portal.jne.gob.pe/"


@register
class JneSource(BaseSource):
    """Query Peru's JNE electoral registry by DNI."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pe.jne",
            display_name="JNE — Jurado Nacional de Elecciones",
            description="Peru electoral registry: voter status and electoral district by DNI",
            country="PE",
            url=JNE_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        dni = input.document_number or input.extra.get("dni", "")
        if not dni:
            raise SourceError("pe.jne", "Must provide document_number (DNI)")
        return self._query(dni=dni, audit=input.audit)

    def _query(self, dni: str, audit: bool = False) -> JneResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("pe.jne", "cedula", dni)

        with browser.page(JNE_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                dni_input = page.query_selector(
                    "input[name='dni'], input[id*='dni' i], "
                    "input[placeholder*='DNI' i], input[type='text']:first-of-type"
                )
                if dni_input:
                    dni_input.fill(dni)
                    logger.info("Filled DNI: %s", dni)
                else:
                    raise SourceError("pe.jne", "DNI input field not found")

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

                page.wait_for_timeout(4000)
                page.wait_for_selector("body", timeout=15000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, dni)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("pe.jne", f"Query failed: {e}") from e

    def _parse_result(self, page, dni: str) -> JneResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = JneResult(queried_at=datetime.now(), dni=dni)
        details: dict = {}

        rows = page.query_selector_all("table tr, .result tr")
        for row in rows:
            cells = row.query_selector_all("td, th")
            if len(cells) >= 2:
                label = (cells[0].inner_text() or "").strip()
                value = (cells[1].inner_text() or "").strip()
                if label and value:
                    details[label] = value
                    label_lower = label.lower()
                    if "nombre" in label_lower:
                        result.nombre = value
                    elif "distrito" in label_lower or "circunscripci" in label_lower:
                        result.electoral_district = value
                    elif "estado" in label_lower or "condici" in label_lower:
                        result.voting_status = value

        if details:
            result.details = details

        # Fallback: body text scan
        if not result.nombre:
            for line in body_text.split("\n"):
                stripped = line.strip()
                lower = stripped.lower()
                if "nombre" in lower and ":" in stripped:
                    result.nombre = stripped.split(":", 1)[1].strip()
                elif (
                    ("distrito" in lower or "circunscripci" in lower)
                    and ":" in stripped
                    and not result.electoral_district
                ):
                    result.electoral_district = stripped.split(":", 1)[1].strip()
                elif (
                    ("estado" in lower or "condici" in lower)
                    and ":" in stripped
                    and not result.voting_status
                ):
                    result.voting_status = stripped.split(":", 1)[1].strip()

        return result
