"""Honduras CNE source — electoral registry.

Queries Honduras' Consejo Nacional Electoral (CNE) for voter
registration data by DNI (cedula).

Flow:
1. Navigate to https://censo.cne.hn/
2. Enter DNI (without hyphens)
3. Submit and parse full name, voting center, electoral district

Source: https://censo.cne.hn/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.hn.cne import HnCneResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CNE_URL = "https://censo.cne.hn/"


@register
class HnCneSource(BaseSource):
    """Query Honduras CNE electoral registry by DNI."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="hn.cne",
            display_name="CNE — Censo Electoral Honduras",
            description="Honduras electoral registry: voter name, voting center, district (CNE)",
            country="HN",
            url=CNE_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CEDULA:
            raise SourceError("hn.cne", f"Only cedula supported, got: {input.document_type}")
        dni = input.document_number.strip().replace("-", "")
        if not dni:
            raise SourceError("hn.cne", "DNI is required")
        return self._query(dni, audit=input.audit)

    def _query(self, dni: str, audit: bool = False) -> HnCneResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("hn.cne", "dni", dni)

        with browser.page(CNE_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill DNI input
                dni_input = page.query_selector(
                    'input[id*="dni"], input[name*="dni"], '
                    'input[id*="cedula"], input[name*="cedula"], '
                    'input[id*="numero"], input[name*="numero"], '
                    'input[type="text"]'
                )
                if not dni_input:
                    raise SourceError("hn.cne", "Could not find DNI input field")

                dni_input.fill(dni)
                logger.info("Filled DNI: %s", dni)

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
                    dni_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, dni)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("hn.cne", f"Query failed: {e}") from e

    def _parse_result(self, page, dni: str) -> HnCneResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = HnCneResult(queried_at=datetime.now(), dni=dni)
        details: dict[str, str] = {}

        field_map = {
            "nombre": "nombre",
            "distrito": "distrito",
            "departamento": "distrito",
            "centro": "centro_votacion",
            "municipio": "centro_votacion",
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
