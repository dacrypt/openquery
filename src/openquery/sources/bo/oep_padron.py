"""Bolivia OEP electoral registry source — padrón electoral.

Queries Bolivia's OEP (Órgano Electoral Plurinacional) portal for electoral registration.

Source: https://yoparticipo.oep.org.bo/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.bo.oep_padron import OepPadronResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

OEP_URL = "https://yoparticipo.oep.org.bo/"


@register
class OepPadronSource(BaseSource):
    """Query Bolivia's OEP electoral registry by cedula."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="bo.oep_padron",
            display_name="OEP — Padrón Electoral",
            description=(
                "Bolivia electoral registry: electoral registration, polling station"
                " (Órgano Electoral Plurinacional)"
            ),
            country="BO",
            url=OEP_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        cedula = input.extra.get("cedula", "") or input.document_number
        if not cedula:
            raise SourceError("bo.oep_padron", "cedula is required")
        return self._query(cedula.strip(), audit=input.audit)

    def _query(self, cedula: str, audit: bool = False) -> OepPadronResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("bo.oep_padron", "cedula", cedula)

        with browser.page(OEP_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                cedula_input = page.query_selector(
                    'input[name*="cedula"], input[name*="ci"], '
                    'input[id*="cedula"], input[id*="ci"], '
                    'input[placeholder*="cédula"], input[placeholder*="CI"], '
                    'input[type="text"]'
                )
                if not cedula_input:
                    raise SourceError("bo.oep_padron", "Could not find cedula input field")

                cedula_input.fill(cedula)
                logger.info("Filled cedula: %s", cedula)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'input[type="submit"], button[type="submit"], '
                    'button:has-text("Buscar"), button:has-text("Consultar"), '
                    'button:has-text("Verificar")'
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
                raise SourceError("bo.oep_padron", f"Query failed: {e}") from e

    def _parse_result(self, page, cedula: str) -> OepPadronResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = OepPadronResult(queried_at=datetime.now(), cedula=cedula)

        field_map = {
            "nombre": "nombre",
            "apellido": "nombre",
            "departamento": "departamento",
            "municipio": "municipio",
            "recinto": "recinto",
            "mesa": "mesa",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_map.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value:
                        setattr(result, field, value)
                    break

        return result
