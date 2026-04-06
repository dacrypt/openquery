"""VTV source — Buenos Aires Province vehicle technical inspection.

Verificación Técnica Vehicular — Province of Buenos Aires.

Queries VTV portal for inspection status and expiration date by plate (dominio).

Flow:
1. Navigate to VTV consultation portal
2. Enter plate (dominio)
3. Submit and parse VTV status and expiry
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ar.vtv import VtvResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

VTV_URL = "https://vtv.gba.gob.ar/consultar-vtv"


@register
class VtvSource(BaseSource):
    """Query Buenos Aires Province VTV vehicle inspection status by plate (dominio)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ar.vtv",
            display_name="VTV — Verificación Técnica Vehicular (Buenos Aires)",
            description=(
                "Buenos Aires Province vehicle technical inspection: status and "
                "expiration date by plate (dominio)"
            ),
            country="AR",
            url=VTV_URL,
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.PLATE:
            raise SourceError("ar.vtv", f"Unsupported document type: {input.document_type}")
        return self._query(input.document_number, audit=input.audit)

    def _query(self, dominio: str, audit: bool = False) -> VtvResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("ar.vtv", "placa", dominio)

        with browser.page(VTV_URL) as page:
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
                    raise SourceError("ar.vtv", "Could not find plate input field")

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
                raise SourceError("ar.vtv", f"Query failed: {e}") from e

    def _parse_result(self, page, dominio: str) -> VtvResult:
        body_text = page.inner_text("body")
        result = VtvResult(placa=dominio.upper())

        # Detect status keywords
        body_lower = body_text.lower()
        if "vigente" in body_lower or "habilitado" in body_lower:
            result.vtv_status = "VIGENTE"
        elif "vencida" in body_lower or "vencido" in body_lower:
            result.vtv_status = "VENCIDA"
        elif "no registra" in body_lower or "sin vtv" in body_lower:
            result.vtv_status = "SIN VTV"

        # Parse expiration date (common formats: DD/MM/YYYY)
        date_match = re.search(
            r"(?:vencimiento|expira|v[aá]lido\s+hasta)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            body_text,
            re.IGNORECASE,
        )
        if date_match:
            result.expiration_date = date_match.group(1).strip()

        # Table-based parsing
        rows = page.query_selector_all("table tr, .resultado tr")
        for row in rows:
            cells = row.query_selector_all("td, th")
            if len(cells) >= 2:
                label = (cells[0].inner_text() or "").strip().lower()
                value = (cells[1].inner_text() or "").strip()
                if "vencimiento" in label or "vigencia" in label:
                    result.expiration_date = result.expiration_date or value
                elif "estado" in label or "situaci" in label:
                    result.vtv_status = result.vtv_status or value.upper()

        result.details = {"raw_text": body_text[:500] if body_text else ""}
        return result
