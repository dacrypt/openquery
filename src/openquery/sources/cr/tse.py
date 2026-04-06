"""Costa Rica TSE electoral registry source — cedula lookup.

Queries the Tribunal Supremo de Elecciones (TSE) for citizen identity data.
ASP.NET WebForms, no CAPTCHA, no login required.

Source: https://servicioselectorales.tse.go.cr/chc/consulta_cedula.aspx
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.cr.tse import CrTseResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

TSE_URL = "https://servicioselectorales.tse.go.cr/chc/consulta_cedula.aspx"


@register
class CrTseSource(BaseSource):
    """Query Costa Rica TSE electoral registry by cedula."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="cr.tse",
            display_name="TSE — Padrón Electoral",
            description=(
                "Costa Rica electoral registry: full name, gender, district, "
                "expiry date, electoral precinct (Tribunal Supremo de Elecciones)"
            ),
            country="CR",
            url=TSE_URL,
            supported_inputs=[DocumentType.CEDULA, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        cedula = input.extra.get("cedula", "") or input.document_number
        if not cedula:
            raise SourceError("cr.tse", "Cédula is required")
        return self._query(cedula.strip(), audit=input.audit)

    def _query(self, cedula: str, audit: bool = False) -> CrTseResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("cr.tse", "cedula", cedula)

        with browser.page(TSE_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                cedula_input = page.query_selector(
                    '#txtcedula, input[name="txtcedula"]'
                )
                if not cedula_input:
                    raise SourceError("cr.tse", "Could not find cedula input field")

                cedula_input.fill(cedula)
                logger.info("Filled cedula: %s", cedula)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    '#btnConsultaCedula, input[name="btnConsultaCedula"]'
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
                raise SourceError("cr.tse", f"Query failed: {e}") from e

    def _parse_result(self, page, cedula: str) -> CrTseResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        result = CrTseResult(
            queried_at=datetime.now(),
            cedula=cedula,
        )

        field_patterns = {
            "nombre": "nombre",
            "género": "genero",
            "genero": "genero",
            "sexo": "genero",
            "distrito": "distrito",
            "fecha de vencimiento": "fecha_vencimiento",
            "vencimiento": "fecha_vencimiento",
            "precinto": "precinto",
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

        result.details = body_text.strip()[:500]

        return result
