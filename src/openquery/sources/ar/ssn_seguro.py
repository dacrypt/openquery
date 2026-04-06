"""SSN Seguro source — Argentine mandatory vehicle insurance check (SSN).

Superintendencia de Seguros de la Nacion — mandatory insurance consultation.

Queries SSN for whether a vehicle has active mandatory insurance (seguro obligatorio)
by plate (dominio).

Flow:
1. Navigate to SSN insurance portal
2. Enter plate (dominio)
3. Submit and parse insurance status, insurer name, and policy validity
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ar.ssn_seguro import SsnSeguroResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SSN_SEGURO_URL = "https://seguro.ssn.gob.ar/"


@register
class SsnSeguroSource(BaseSource):
    """Query SSN for mandatory vehicle insurance status by plate (dominio)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ar.ssn_seguro",
            display_name="SSN — Seguro Obligatorio Automotor",
            description=(
                "Argentine mandatory vehicle insurance check: insurer and policy validity "
                "by plate (dominio)"
            ),
            country="AR",
            url=SSN_SEGURO_URL,
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.PLATE:
            raise SourceError(
                "ar.ssn_seguro", f"Unsupported document type: {input.document_type}"
            )
        return self._query(input.document_number, audit=input.audit)

    def _query(self, dominio: str, audit: bool = False) -> SsnSeguroResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("ar.ssn_seguro", "placa", dominio)

        with browser.page(SSN_SEGURO_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Find plate input field
                plate_input = page.query_selector(
                    'input[name*="dominio" i], input[name*="patente" i], '
                    'input[placeholder*="dominio" i], input[placeholder*="patente" i], '
                    'input[type="text"]'
                )
                if not plate_input:
                    raise SourceError("ar.ssn_seguro", "Could not find plate input field")

                plate_input.fill(dominio.upper())
                logger.info("Filled dominio: %s", dominio)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit form
                submit = page.query_selector(
                    'button:has-text("Consultar"), button:has-text("Buscar"), '
                    'input[type="submit"], button[type="submit"]'
                )
                if submit:
                    submit.click()
                else:
                    plate_input.press("Enter")

                page.wait_for_timeout(3000)
                page.wait_for_selector("body", timeout=15000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, dominio)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("ar.ssn_seguro", f"Query failed: {e}") from e

    def _parse_result(self, page, dominio: str) -> SsnSeguroResult:
        body_text = page.inner_text("body")
        result = SsnSeguroResult(placa=dominio.upper())

        body_lower = body_text.lower()

        # Detect insurance presence
        if (
            "tiene seguro" in body_lower
            or "cobertura vigente" in body_lower
            or "asegurado" in body_lower
        ):
            result.has_insurance = True
        if (
            "sin seguro" in body_lower
            or "no tiene seguro" in body_lower
            or "no registra" in body_lower
        ):
            result.has_insurance = False

        # Detect policy validity
        if "vigente" in body_lower or "v[aá]lido" in body_lower:
            result.policy_valid = True

        # Table-based parsing for insurer and validity
        rows = page.query_selector_all("table tr, .resultado tr")
        for row in rows:
            cells = row.query_selector_all("td, th")
            if len(cells) >= 2:
                label = (cells[0].inner_text() or "").strip().lower()
                value = (cells[1].inner_text() or "").strip()
                if "aseguradora" in label or "compa" in label or "entidad" in label:
                    result.insurer = result.insurer or value
                elif "estado" in label or "situaci" in label:
                    if "vigente" in value.lower():
                        result.policy_valid = True
                elif "cobertura" in label:
                    result.insurer = result.insurer or value

        result.details = {"raw_text": body_text[:500] if body_text else ""}
        return result
