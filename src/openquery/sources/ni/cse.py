"""Nicaragua CSE source — electoral/cedula lookup.

Queries the CSE (Consejo Supremo Electoral) portal for voter status and
voting center information by cedula number.
Browser-based, public, no authentication required.

Source: https://www.cse.gob.ni/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ni.cse import NiCseResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CSE_URL = "https://www.cse.gob.ni/"


@register
class NiCseSource(BaseSource):
    """Query Nicaragua CSE electoral registry by cedula number."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ni.cse",
            display_name="CSE — Consulta de Cédula Electoral",
            description=(
                "Nicaragua electoral registry: voter status, voting center, "
                "and municipality (Consejo Supremo Electoral)"
            ),
            country="NI",
            url=CSE_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        cedula = input.extra.get("cedula", "") or input.document_number
        if not cedula:
            raise SourceError("ni.cse", "Cédula is required")
        return self._query(cedula.strip(), audit=input.audit)

    def _query(self, cedula: str, audit: bool = False) -> NiCseResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("ni.cse", "cedula", cedula)

        with browser.page(CSE_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                cedula_input = page.query_selector(
                    '#txtCedula, input[name="txtCedula"], '
                    '#cedula, input[name="cedula"], '
                    'input[placeholder*="édula"], input[placeholder*="cedula"]'
                )
                if not cedula_input:
                    raise SourceError("ni.cse", "Could not find cedula input field")

                cedula_input.fill(cedula)
                logger.info("Filled cedula: %s", cedula)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    '#btnBuscar, input[name="btnBuscar"], '
                    '#btnConsultar, input[name="btnConsultar"], '
                    'button[type="submit"]'
                )
                if submit:
                    submit.click()
                else:
                    cedula_input.press("Enter")

                page.wait_for_timeout(3000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, cedula)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("ni.cse", f"Query failed: {e}") from e

    def _parse_result(self, page, cedula: str) -> NiCseResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = NiCseResult(queried_at=datetime.now(), cedula=cedula)

        field_map = {
            "nombre": "nombre",
            "junta": "voting_center",
            "centro": "voting_center",
            "recinto": "voting_center",
            "municipio": "municipality",
            "municipalidad": "municipality",
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

        result.details = {"raw": body_text.strip()[:500]}

        return result
