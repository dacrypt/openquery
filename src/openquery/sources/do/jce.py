"""Dominican Republic JCE source — cedula verification.

Queries the Junta Central Electoral (JCE) for cedula identity validation.

Source: https://dataportal.jce.gob.do/sarc/validar-certificacion-cedula/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.do.jce import DoJceResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

JCE_URL = "https://dataportal.jce.gob.do/sarc/validar-certificacion-cedula/"


@register
class DoJceSource(BaseSource):
    """Query Dominican Republic JCE cedula verification."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="do.jce",
            display_name="JCE — Validar Cédula",
            description="Dominican Republic identity validation: cedula status (Junta Central Electoral)",
            country="DO",
            url=JCE_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        cedula = input.document_number or input.extra.get("cedula", "")
        if not cedula:
            raise SourceError("do.jce", "Cédula is required")
        return self._query(cedula.strip(), audit=input.audit)

    def _query(self, cedula: str, audit: bool = False) -> DoJceResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("do.jce", "cedula", cedula)

        with browser.page(JCE_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                cedula_input = page.query_selector(
                    'input[name*="cedula"], input[id*="cedula"], '
                    'input[placeholder*="dula"], input[type="text"]'
                )
                if not cedula_input:
                    raise SourceError("do.jce", "Could not find cédula input field")

                cedula_input.fill(cedula)
                logger.info("Filled cédula: %s", cedula)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button:has-text("Validar"), button:has-text("Buscar")'
                )
                if submit:
                    submit.click()
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
                raise SourceError("do.jce", f"Query failed: {e}") from e

    def _parse_result(self, page, cedula: str) -> DoJceResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = DoJceResult(queried_at=datetime.now(), cedula=cedula)

        field_map = {
            "nombre": "nombre",
            "estado": "estado",
        }

        lines = body_text.split("\n")
        for line in lines:
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_map.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    setattr(result, field, value)
                    break

        if body_text.strip():
            result.details = body_text.strip()[:500]

        return result
