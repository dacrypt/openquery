"""Costa Rica Ministerio de Hacienda tax declarant status source.

Queries the Hacienda TICA portal for tax declarant status and obligations.
Browser-based, public, no authentication required.

Source: https://ticaconsultas.hacienda.go.cr/Tica/hrgdeclarantescedula.aspx
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.cr.hacienda import CrHaciendaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

HACIENDA_URL = "https://ticaconsultas.hacienda.go.cr/Tica/hrgdeclarantescedula.aspx"


@register
class CrHaciendaSource(BaseSource):
    """Query Costa Rica Hacienda TICA portal by cedula (natural or jurídica)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="cr.hacienda",
            display_name="Hacienda — Consulta de Declarantes",
            description=(
                "Costa Rica tax declarant status and obligations by cedula "
                "(Ministerio de Hacienda TICA portal)"
            ),
            country="CR",
            url=HACIENDA_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        cedula = input.extra.get("cedula", "") or input.document_number
        if not cedula:
            raise SourceError("cr.hacienda", "Cédula is required")
        return self._query(cedula.strip(), audit=input.audit)

    def _query(self, cedula: str, audit: bool = False) -> CrHaciendaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("cr.hacienda", "cedula", cedula)

        with browser.page(HACIENDA_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                cedula_input = page.query_selector(
                    '#txtCedula, input[name="txtCedula"], #txtcedula, input[name="txtcedula"]'
                )
                if not cedula_input:
                    raise SourceError("cr.hacienda", "Could not find cedula input field")

                cedula_input.fill(cedula)
                logger.info("Filled cedula: %s", cedula)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    '#btnConsultar, input[name="btnConsultar"], '
                    '#btnBuscar, input[name="btnBuscar"], '
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
                raise SourceError("cr.hacienda", f"Query failed: {e}") from e

    def _parse_result(self, page, cedula: str) -> CrHaciendaResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        result = CrHaciendaResult(
            queried_at=datetime.now(),
            cedula=cedula,
        )

        field_patterns = {
            "estado": "declarant_status",
            "condición": "declarant_status",
            "condicion": "declarant_status",
            "declarante": "declarant_status",
            "obligación": "obligations",
            "obligacion": "obligations",
            "obligaciones": "obligations",
            "impuesto": "obligations",
            "tributo": "obligations",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_patterns.items():
                if lower.startswith(label) and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value:
                        setattr(result, field, value)
                    break

        result.details = body_text.strip()[:500]

        return result
