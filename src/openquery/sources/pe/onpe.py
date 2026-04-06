"""ONPE source — Peru electoral processes lookup.

Queries Peru's ONPE for electoral participation and assigned location by DNI.

Flow:
1. Navigate to the ONPE portal
2. Enter DNI number
3. Submit and parse electoral location and participation data

Source: https://www.onpe.gob.pe/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pe.onpe import OnpeResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

ONPE_URL = "https://www.onpe.gob.pe/"


@register
class OnpeSource(BaseSource):
    """Query Peru's ONPE electoral processes by DNI."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pe.onpe",
            display_name="ONPE — Oficina Nacional de Procesos Electorales",
            description="Peru electoral participation: assigned voting location and electoral data by DNI",  # noqa: E501
            country="PE",
            url=ONPE_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        dni = input.document_number or input.extra.get("dni", "")
        if not dni:
            raise SourceError("pe.onpe", "Must provide document_number (DNI)")
        return self._query(dni=dni, audit=input.audit)

    def _query(self, dni: str, audit: bool = False) -> OnpeResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("pe.onpe", "cedula", dni)

        with browser.page(ONPE_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                dni_input = page.query_selector(
                    "input[name='dni'], input[id*='dni' i], "
                    "input[placeholder*='DNI' i], input[type='text']:first-of-type"
                )
                if dni_input:
                    dni_input.fill(dni)
                    logger.info("Filled DNI: %s", dni)
                else:
                    raise SourceError("pe.onpe", "DNI input field not found")

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    "button[type='submit'], input[type='submit'], "
                    "button:has-text('Buscar'), button:has-text('Consultar')"
                )
                if submit:
                    submit.click()
                else:
                    page.keyboard.press("Enter")

                page.wait_for_timeout(4000)
                page.wait_for_selector("body", timeout=15000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, dni)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("pe.onpe", f"Query failed: {e}") from e

    def _parse_result(self, page, dni: str) -> OnpeResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = OnpeResult(queried_at=datetime.now(), dni=dni)
        details: dict = {}

        rows = page.query_selector_all("table tr, .result tr")
        for row in rows:
            cells = row.query_selector_all("td, th")
            if len(cells) >= 2:
                label = (cells[0].inner_text() or "").strip()
                value = (cells[1].inner_text() or "").strip()
                if label and value:
                    details[label] = value
                    label_lower = label.lower()
                    if "nombre" in label_lower:
                        result.nombre = value
                    elif "local" in label_lower or "ubicaci" in label_lower or "mesa" in label_lower:  # noqa: E501
                        result.electoral_location = value

        if details:
            result.details = details

        # Fallback: body text scan
        if not result.nombre:
            for line in body_text.split("\n"):
                stripped = line.strip()
                lower = stripped.lower()
                if "nombre" in lower and ":" in stripped:
                    result.nombre = stripped.split(":", 1)[1].strip()
                elif (
                    ("local" in lower or "ubicaci" in lower or "mesa" in lower)
                    and ":" in stripped
                    and not result.electoral_location
                ):
                    result.electoral_location = stripped.split(":", 1)[1].strip()

        return result
