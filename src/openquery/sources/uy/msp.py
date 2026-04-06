"""Uruguay MSP health facility registry source.

Queries MSP (Ministerio de Salud Pública) for health facility
permits and registration data by facility name.

URL: https://www.gub.uy/ministerio-salud-publica/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.uy.msp import UyMspResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

MSP_URL = "https://www.gub.uy/ministerio-salud-publica/"


@register
class UyMspSource(BaseSource):
    """Query Uruguay MSP for health facility permit data."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="uy.msp",
            display_name="MSP — Registro Establecimientos Salud Uruguay",
            description=(
                "Uruguay MSP health ministry: facility permits "
                "and health registry status by facility name"
            ),
            country="UY",
            url=MSP_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query MSP for health facility data."""
        search_term = input.extra.get("facility_name", "") or input.document_number
        if not search_term:
            raise SourceError("uy.msp", "facility_name is required")
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> UyMspResult:
        """Full flow: launch browser, fill form, parse results."""
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("uy.msp", "facility_name", search_term)

        with browser.page(MSP_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[id*="establecimiento"], input[name*="establecimiento"], '
                    'input[id*="nombre"], input[name*="nombre"], '
                    'input[id*="search"], input[name*="search"], '
                    'input[type="text"], input[type="search"]'
                )
                if not search_input:
                    raise SourceError("uy.msp", "Could not find search input field")

                search_input.fill(search_term)
                logger.info("Filled search term: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button:has-text("Buscar"), button:has-text("Consultar")'
                )
                if submit:
                    submit.click()
                else:
                    search_input.press("Enter")

                page.wait_for_timeout(3000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_term)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("uy.msp", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> UyMspResult:
        """Parse health facility data from the page DOM."""
        body_text = page.inner_text("body")
        result = UyMspResult(search_term=search_term)
        details: dict[str, str] = {}

        field_map = {
            "facility name": "facility_name",
            "nombre del establecimiento": "facility_name",
            "nombre de establecimiento": "facility_name",
            "nombre": "facility_name",
            "permit status": "permit_status",
            "estado del permiso": "permit_status",
            "estado de habilitación": "permit_status",
            "habilitación": "permit_status",
            "estado": "permit_status",
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
            "MSP result — facility=%s, permit_status=%s",
            result.facility_name,
            result.permit_status,
        )
        return result
