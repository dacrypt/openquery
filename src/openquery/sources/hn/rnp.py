"""Honduras RNP source — identity / DNI registry.

Queries Honduras' Registro Nacional de las Personas (RNP)
for identity data by DNI (cédula).

Flow:
1. Navigate to https://www.rnp.hn/
2. Enter DNI
3. Submit and parse name, birth date, address info

Source: https://www.rnp.hn/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.hn.rnp import HnRnpResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

RNP_URL = "https://www.rnp.hn/"


@register
class HnRnpSource(BaseSource):
    """Query Honduras RNP identity registry by DNI."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="hn.rnp",
            display_name="RNP — Registro Nacional de las Personas Honduras",
            description="Honduras identity registry: name, birth date, address (Registro Nacional de las Personas)",  # noqa: E501
            country="HN",
            url=RNP_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CEDULA:
            raise SourceError("hn.rnp", f"Only cedula (DNI) supported, got: {input.document_type}")
        dni = input.document_number.strip().replace("-", "")
        if not dni:
            raise SourceError("hn.rnp", "DNI is required")
        return self._query(dni, audit=input.audit)

    def _query(self, dni: str, audit: bool = False) -> HnRnpResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("hn.rnp", "dni", dni)

        with browser.page(RNP_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill DNI input
                dni_input = page.query_selector(
                    'input[id*="dni"], input[name*="dni"], '
                    'input[id*="cedula"], input[name*="cedula"], '
                    'input[id*="identidad"], input[name*="identidad"], '
                    'input[id*="numero"], input[name*="numero"], '
                    'input[type="text"]'
                )
                if not dni_input:
                    raise SourceError("hn.rnp", "Could not find DNI input field")

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
                raise SourceError("hn.rnp", f"Query failed: {e}") from e

    def _parse_result(self, page, dni: str) -> HnRnpResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = HnRnpResult(queried_at=datetime.now(), dni=dni)
        details: dict[str, str] = {}

        field_map = {
            "nombre": "nombre",
            "nacimiento": "birth_date",
            "fecha": "birth_date",
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
