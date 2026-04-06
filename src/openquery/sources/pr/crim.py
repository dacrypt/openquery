"""CRIM property tax/catastro source — Puerto Rico.

Queries Puerto Rico's CRIM (Centro de Recaudación de Ingresos Municipales)
catastro system for property tax and valuation data.

Flow:
1. Navigate to https://catastro.crimpr.net/cdprpc/
2. Wait for search form to load
3. Fill property account number or parcel ID
4. Submit and parse results
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pr.crim import CrimResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CRIM_URL = "https://catastro.crimpr.net/cdprpc/"


@register
class CrimSource(BaseSource):
    """Query Puerto Rico's CRIM property tax/catastro system."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pr.crim",
            display_name="CRIM — Catastro Puerto Rico",
            description=(
                "Puerto Rico CRIM property tax and catastro: value, tax status, owner info"
            ),
            country="PR",
            url=CRIM_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query CRIM for property tax/catastro data."""
        search_term = (
            input.extra.get("account_number", "")
            or input.extra.get("parcel_id", "")
            or input.document_number
        )
        if not search_term:
            raise SourceError("pr.crim", "account_number or parcel_id is required")
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> CrimResult:
        """Full flow: launch browser, fill form, parse results."""
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("pr.crim", "account_number", search_term)

        with browser.page(CRIM_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Find search input
                search_input = page.query_selector(
                    'input[id*="account"], input[name*="account"], '
                    'input[id*="parcel"], input[name*="parcel"], '
                    'input[id*="catastro"], input[name*="catastro"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("pr.crim", "Could not find search input field")

                search_input.fill(search_term)
                logger.info("Filled search term: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button:has-text("Buscar"), button:has-text("Search"), '
                    'button:has-text("Consultar")'
                )
                if submit:
                    submit.click()
                else:
                    search_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_term)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("pr.crim", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> CrimResult:
        """Parse property data from the page DOM."""
        body_text = page.inner_text("body")
        result = CrimResult(account_number=search_term)
        details: dict[str, str] = {}

        field_map = {
            "valor": "property_value",
            "value": "property_value",
            "tasación": "property_value",
            "tasacion": "property_value",
            "estado": "tax_status",
            "status": "tax_status",
            "dueño": "owner",
            "dueno": "owner",
            "owner": "owner",
            "propietario": "owner",
            "dirección": "address",
            "direccion": "address",
            "address": "address",
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
            "CRIM result — account=%s, owner=%s, status=%s",
            result.account_number, result.owner, result.tax_status,
        )
        return result
