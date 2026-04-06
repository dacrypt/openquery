"""Autopase source — TAG highway toll debt status (Chile).

Queries the Autopase portal for TAG account balance and debt status by vehicle plate.

Flow:
1. Navigate to the Autopase TAG estado page
2. Enter the plate number
3. Submit and parse TAG status and debt amount
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.cl.autopase import AutopaseResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

AUTOPASE_URL = "https://www.autopase.cl/tag/estado"


@register
class AutopaseSource(BaseSource):
    """Query Autopase for TAG highway toll account and debt status by plate."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="cl.autopase",
            display_name="Autopase — Estado TAG Autopista",
            description="TAG highway toll account balance and debt status from Chile's Autopase portal",  # noqa: E501
            country="CL",
            url=AUTOPASE_URL,
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        plate = input.document_number
        if not plate:
            raise SourceError("cl.autopase", "Plate number is required")
        return self._query(plate, audit=input.audit)

    def _query(self, plate: str, audit: bool = False) -> AutopaseResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("cl.autopase", "plate", plate)

        with browser.page(AUTOPASE_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill plate input
                plate_input = page.query_selector(
                    'input[name*="placa"], input[name*="Placa"], '
                    'input[placeholder*="placa"], input[placeholder*="Patente"], '
                    'input[name*="patente"], input[id*="patente"], '
                    'input[id*="placa"], input[type="text"]'
                )
                if not plate_input:
                    raise SourceError("cl.autopase", "Could not find plate input field")
                plate_input.fill(plate)
                logger.info("Filled plate: %s", plate)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit = page.query_selector(
                    'input[type="submit"], button[type="submit"], '
                    "button:has-text('Consultar'), button:has-text('Buscar'), "
                    "button:has-text('Ver estado'), input[value='Consultar']"
                )
                if submit:
                    submit.click()
                else:
                    plate_input.press("Enter")

                page.wait_for_timeout(3000)
                page.wait_for_selector("body", timeout=15000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, plate)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("cl.autopase", f"Query failed: {e}") from e

    def _parse_result(self, page, plate: str) -> AutopaseResult:
        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        result = AutopaseResult(placa=plate)

        # Parse TAG status — require a colon to avoid matching headings like "Estado TAG Autopista"
        m = re.search(
            r"(?:estado\s*tag|estado\s*cuenta|estado)\s*:\s*([^\n]+)",
            body_text,
            re.IGNORECASE,
        )
        if m:
            result.tag_status = m.group(1).strip()

        # Parse debt amount — look for currency values
        m = re.search(
            r"(?:deuda|saldo\s*deudor|monto)[:\s]+\$?\s*([\d.,]+)",
            body_text,
            re.IGNORECASE,
        )
        if m:
            result.debt_amount = m.group(1).strip()

        # Infer status from keywords if not found
        if not result.tag_status:
            no_debt_keywords = ["sin deuda", "al d[ií]a", "sin mora", "saldo cero"]
            debt_keywords = ["deuda", "mora", "pendiente", "adeuda"]
            if any(re.search(kw, body_lower) for kw in no_debt_keywords):
                result.tag_status = "Sin deuda"
            elif any(re.search(kw, body_lower) for kw in debt_keywords):
                result.tag_status = "Con deuda"

        # Parse table rows for structured details
        rows = page.query_selector_all("table tr, .resultado tr, .estado tr")
        details: dict[str, str] = {}
        for row in rows:
            cells = row.query_selector_all("td, th")
            if len(cells) >= 2:
                key = (cells[0].inner_text() or "").strip()
                val = (cells[1].inner_text() or "").strip()
                if key and val:
                    details[key] = val
                    key_lower = key.lower()
                    if "estado" in key_lower:
                        result.tag_status = result.tag_status or val
                    if "deuda" in key_lower or "monto" in key_lower or "saldo" in key_lower:
                        result.debt_amount = result.debt_amount or val

        result.details = details

        return result
