"""El Salvador TSE source — electoral registry / DUI lookup.

Queries El Salvador's Tribunal Supremo Electoral (TSE) for voter
registration data by DUI number.

Flow:
1. Navigate to https://consulta.tse.gob.sv/
2. Enter DUI number
3. Submit and parse full name, voting center, municipality

Source: https://consulta.tse.gob.sv/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.sv.tse import SvTseResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

TSE_URL = "https://consulta.tse.gob.sv/"


@register
class SvTseSource(BaseSource):
    """Query El Salvador TSE electoral registry by DUI."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="sv.tse",
            display_name="TSE — Consulta Electoral El Salvador",
            description="El Salvador electoral registry: voter name, voting center, municipality",
            country="SV",
            url=TSE_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CEDULA:
            raise SourceError("sv.tse", f"Only cedula (DUI) supported, got: {input.document_type}")
        dui = input.document_number.strip()
        if not dui:
            raise SourceError("sv.tse", "DUI is required")
        return self._query(dui, audit=input.audit)

    def _query(self, dui: str, audit: bool = False) -> SvTseResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("sv.tse", "dui", dui)

        with browser.page(TSE_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill DUI input
                dui_input = page.query_selector(
                    'input[id*="dui"], input[name*="dui"], '
                    'input[id*="DUI"], input[name*="DUI"], '
                    'input[id*="cedula"], input[name*="cedula"], '
                    'input[type="text"]'
                )
                if not dui_input:
                    raise SourceError("sv.tse", "Could not find DUI input field")

                dui_input.fill(dui)
                logger.info("Filled DUI: %s", dui)

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
                    dui_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, dui)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("sv.tse", f"Query failed: {e}") from e

    def _parse_result(self, page, dui: str) -> SvTseResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = SvTseResult(queried_at=datetime.now(), dui=dui)
        details: dict[str, str] = {}

        field_map = {
            "nombre": "nombre",
            "centro": "centro_votacion",
            "municipio": "municipio",
            "municipalidad": "municipio",
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
