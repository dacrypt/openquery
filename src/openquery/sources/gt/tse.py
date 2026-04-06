"""Guatemala TSE source — electoral registry / DPI lookup.

Queries Guatemala's Tribunal Supremo Electoral (TSE) for voter
registration data by DPI number.

Flow:
1. Navigate to TSE affiliation query page
2. Enter DPI number
3. Submit and parse electoral status, polling location, affiliation

Source: https://www.tse.org.gt/reg-ciudadanos/sistema-de-estadisticas/consulta-de-afiliacion
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.gt.tse import GtTseResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

TSE_URL = "https://www.tse.org.gt/reg-ciudadanos/sistema-de-estadisticas/consulta-de-afiliacion"


@register
class GtTseSource(BaseSource):
    """Query Guatemala TSE electoral registry by DPI."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="gt.tse",
            display_name="TSE — Consulta de Afiliación Guatemala",
            description="Guatemala electoral registry: status, polling location, affiliation (TSE)",
            country="GT",
            url=TSE_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CEDULA:
            raise SourceError("gt.tse", f"Only cedula (DPI) supported, got: {input.document_type}")
        dpi = input.document_number.strip()
        if not dpi:
            raise SourceError("gt.tse", "DPI is required")
        return self._query(dpi, audit=input.audit)

    def _query(self, dpi: str, audit: bool = False) -> GtTseResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("gt.tse", "dpi", dpi)

        with browser.page(TSE_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill DPI input
                dpi_input = page.query_selector(
                    'input[id*="dpi"], input[name*="dpi"], '
                    'input[id*="DPI"], input[name*="DPI"], '
                    'input[id*="cui"], input[name*="cui"], '
                    'input[id*="CUI"], input[name*="CUI"], '
                    'input[type="text"]'
                )
                if not dpi_input:
                    raise SourceError("gt.tse", "Could not find DPI input field")

                dpi_input.fill(dpi)
                logger.info("Filled DPI: %s", dpi)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="consultar"], button[id*="buscar"], '
                    'button:has-text("Consultar"), button:has-text("Buscar")'
                )
                if submit:
                    submit.click()
                else:
                    dpi_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, dpi)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("gt.tse", f"Query failed: {e}") from e

    def _parse_result(self, page, dpi: str) -> GtTseResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = GtTseResult(queried_at=datetime.now(), dpi=dpi)
        details: dict[str, str] = {}

        field_map = {
            "nombre": "nombre",
            "estado": "estado_electoral",
            "lugar": "lugar_votacion",
            "centro": "lugar_votacion",
            "municipio": "municipio",
            "municipalidad": "municipio",
            "afiliacion": "afiliacion",
            "afiliación": "afiliacion",
            "partido": "afiliacion",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            lower = stripped.lower()
            for label, attr in field_map.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value:
                        setattr(result, attr, value)
                    break
            # Collect all key:value pairs into details
            if ":" in stripped:
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip()
                if key and val:
                    details[key] = val

        result.details = details
        return result
