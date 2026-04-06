"""Puerto Rico Hacienda SURI tax/merchant registry source.

Queries the SURI portal for merchant registration and tax filing status.

Flow:
1. Navigate to https://suri.hacienda.pr.gov/
2. Wait for search form to load
3. Fill merchant registry number or taxpayer ID
4. Submit and parse results
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pr.hacienda import HaciendaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

HACIENDA_URL = "https://suri.hacienda.pr.gov/"


@register
class HaciendaSource(BaseSource):
    """Query Puerto Rico Hacienda SURI for merchant/taxpayer registry data."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pr.hacienda",
            display_name="Hacienda SURI — Registro de Comerciantes PR",
            description=(
                "Puerto Rico Department of Treasury SURI: "
                "merchant registration, tax filing status, taxpayer ID lookup"
            ),
            country="PR",
            url=HACIENDA_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query SURI for merchant/taxpayer data."""
        search_value = (
            input.extra.get("merchant_number", "")
            or input.extra.get("taxpayer_id", "")
            or input.document_number
        )
        if not search_value:
            raise SourceError("pr.hacienda", "merchant_number or taxpayer_id is required")
        return self._query(search_value.strip(), audit=input.audit)

    def _query(self, search_value: str, audit: bool = False) -> HaciendaResult:
        """Full flow: launch browser, fill form, parse results."""
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("pr.hacienda", "search_value", search_value)

        with browser.page(HACIENDA_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[id*="merchant"], input[name*="merchant"], '
                    'input[id*="contribuyente"], input[name*="contribuyente"], '
                    'input[id*="search"], input[name*="search"], '
                    'input[id*="ruc"], input[name*="ruc"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("pr.hacienda", "Could not find search input field")

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
                raise SourceError("pr.hacienda", f"Query failed: {e}") from e

    def _parse_result(self, page, search_value: str) -> HaciendaResult:
        """Parse merchant/tax data from the page DOM."""
        body_text = page.inner_text("body")
        result = HaciendaResult(search_value=search_value)
        details: dict[str, str] = {}

        field_map = {
            "merchant name": "merchant_name",
            "nombre del comerciante": "merchant_name",
            "registration status": "registration_status",
            "estado de registro": "registration_status",
            "tax status": "tax_status",
            "estado contributivo": "tax_status",
            "nombre": "merchant_name",
            "name": "merchant_name",
            "estado": "tax_status",
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
            if ":" in stripped:
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip()
                if key and val:
                    details[key] = val

        result.details = details
        logger.info(
            "Hacienda result — merchant=%s, tax_status=%s, registration_status=%s",
            result.merchant_name,
            result.tax_status,
            result.registration_status,
        )
        return result
