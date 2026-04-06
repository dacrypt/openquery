"""Puerto Rico DTOP traffic fines source.

Queries the DTOP portal for traffic violations and outstanding fines
by vehicle plate or driver's license number.

Flow:
1. Navigate to https://dtop.pr.gov/
2. Wait for search form to load
3. Fill plate or license number
4. Submit and parse results
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pr.multas import MultasResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

MULTAS_URL = "https://dtop.pr.gov/"


@register
class MultasSource(BaseSource):
    """Query Puerto Rico DTOP for traffic fines by plate or license number."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pr.multas",
            display_name="DTOP — Multas de Tránsito PR",
            description=(
                "Puerto Rico DTOP traffic fines: outstanding violations, "
                "amounts, and payment status by plate or license number"
            ),
            country="PR",
            url=MULTAS_URL,
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query DTOP for traffic fines data."""
        search_value = (
            input.extra.get("plate", "")
            or input.extra.get("license_number", "")
            or input.document_number
        )
        if not search_value:
            raise SourceError("pr.multas", "plate or license_number is required")
        return self._query(search_value.strip(), audit=input.audit)

    def _query(self, search_value: str, audit: bool = False) -> MultasResult:
        """Full flow: launch browser, fill form, parse results."""
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("pr.multas", "search_value", search_value)

        with browser.page(MULTAS_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[id*="plate"], input[name*="plate"], '
                    'input[id*="tablilla"], input[name*="tablilla"], '
                    'input[id*="licencia"], input[name*="licencia"], '
                    'input[id*="license"], input[name*="license"], '
                    'input[id*="search"], input[name*="search"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("pr.multas", "Could not find search input field")

                search_input.fill(search_value)
                logger.info("Filled search value: %s", search_value)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button:has-text("Search"), button:has-text("Buscar"), '
                    'button:has-text("Consultar")'
                )
                if submit:
                    submit.click()
                else:
                    search_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_value)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("pr.multas", f"Query failed: {e}") from e

    def _parse_result(self, page, search_value: str) -> MultasResult:
        """Parse traffic fines data from the page DOM."""
        body_text = page.inner_text("body")
        result = MultasResult(search_value=search_value)
        details: dict[str, str] = {}

        field_map = {
            "total fines": "fines_amount",
            "total multas": "fines_amount",
            "amount due": "fines_amount",
            "total a pagar": "fines_amount",
            "balance": "fines_amount",
        }

        fine_count = 0
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
            # Count fine entries
            if any(kw in lower for kw in ("multa", "violation", "infracción", "infraccion")):
                fine_count += 1
            if ":" in stripped:
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip()
                if key and val:
                    details[key] = val

        if fine_count:
            result.total_fines = fine_count
        result.details = details
        logger.info(
            "Multas result — total_fines=%s, fines_amount=%s",
            result.total_fines, result.fines_amount,
        )
        return result
