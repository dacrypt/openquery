"""CETA source — DNRPA transfer certificate status.

Certificado de Transferencia Automotor — DNRPA.

Queries DNRPA for CETA (vehicle transfer certificate) status by plate (dominio).

Flow:
1. Navigate to DNRPA CETA portal
2. Enter plate (dominio)
3. Submit and parse CETA status, issuance and expiration dates
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ar.ceta import CetaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CETA_URL = "https://www.dnrpa.gov.ar/portal_dnrpa/fabr_import2.php?EstadoCertificado=true"


@register
class CetaSource(BaseSource):
    """Query DNRPA for vehicle transfer certificate (CETA) status by plate (dominio)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ar.ceta",
            display_name="CETA — Certificado de Transferencia Automotor (DNRPA)",
            description=(
                "Argentine vehicle transfer certificate status: validity, issuance and "
                "expiration dates by plate (dominio)"
            ),
            country="AR",
            url=CETA_URL,
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.PLATE:
            raise SourceError("ar.ceta", f"Unsupported document type: {input.document_type}")
        return self._query(input.document_number, audit=input.audit)

    def _query(self, dominio: str, audit: bool = False) -> CetaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("ar.ceta", "placa", dominio)

        with browser.page(CETA_URL) as page:
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
                    raise SourceError("ar.ceta", "Could not find plate input field")

                plate_input.fill(dominio.upper())
                logger.info("Filled dominio: %s", dominio)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit form
                submit = page.query_selector(
                    'button:has-text("Consultar"), button:has-text("Buscar"), '
                    'input[value*="Consultar" i], input[type="submit"], button[type="submit"]'
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
                raise SourceError("ar.ceta", f"Query failed: {e}") from e

    def _parse_result(self, page, dominio: str) -> CetaResult:
        body_text = page.inner_text("body")
        result = CetaResult(placa=dominio.upper())

        body_lower = body_text.lower()

        # Detect CETA status keywords
        if "vigente" in body_lower or "v[aá]lido" in body_lower:
            result.ceta_status = "VIGENTE"
        elif "vencido" in body_lower or "vencida" in body_lower:
            result.ceta_status = "VENCIDO"
        elif "no registra" in body_lower or "sin ceta" in body_lower:
            result.ceta_status = "SIN CETA"

        # Parse dates (DD/MM/YYYY)
        issuance_match = re.search(
            r"(?:emisi[oó]n|fecha\s+de\s+emisi[oó]n|otorgamiento)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            body_text,
            re.IGNORECASE,
        )
        if issuance_match:
            result.issuance_date = issuance_match.group(1).strip()

        expiration_match = re.search(
            r"(?:vencimiento|expiraci[oó]n|v[aá]lido\s+hasta)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            body_text,
            re.IGNORECASE,
        )
        if expiration_match:
            result.expiration_date = expiration_match.group(1).strip()

        # Table-based parsing
        rows = page.query_selector_all("table tr, .resultado tr")
        for row in rows:
            cells = row.query_selector_all("td, th")
            if len(cells) >= 2:
                label = (cells[0].inner_text() or "").strip().lower()
                value = (cells[1].inner_text() or "").strip()
                if "estado" in label or "situaci" in label:
                    result.ceta_status = result.ceta_status or value.upper()
                elif "emisi" in label or "otorgamiento" in label:
                    result.issuance_date = result.issuance_date or value
                elif "vencimiento" in label or "expira" in label:
                    result.expiration_date = result.expiration_date or value

        result.details = {"raw_text": body_text[:500] if body_text else ""}
        return result
