"""Salud source — Puerto Rico Department of Health facility lookup.

Queries the PR Department of Health for health facility license status.

Source: https://www.salud.pr.gov/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pr.salud import PrSaludResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SALUD_URL = "https://www.salud.pr.gov/"


@register
class PrSaludSource(BaseSource):
    """Query Puerto Rico Department of Health facility licenses by name."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pr.salud",
            display_name="Salud PR — Licencias de Facilidades",
            description=(
                "Puerto Rico Department of Health: health facility license lookup by facility name"
            ),
            country="PR",
            url=SALUD_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("facility_name", "") or input.document_number.strip()
        if not search_term:
            raise SourceError("pr.salud", "Facility name is required")
        return self._query(search_term=search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> PrSaludResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("pr.salud", "facility_name", search_term)

        with browser.page(SALUD_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "page_loaded")

                search_input = page.query_selector(
                    'input[name*="facilidad"], input[id*="facilidad"], '
                    'input[name*="search"], input[type="search"], '
                    'input[type="text"], input[placeholder*="facility"]'
                )
                if search_input:
                    search_input.fill(search_term)
                    logger.info("Querying PR Salud for facility: %s", search_term)

                    submit_btn = page.query_selector(
                        'button[type="submit"], input[type="submit"], '
                        'button:has-text("Buscar"), button:has-text("Search")'
                    )
                    if submit_btn:
                        submit_btn.click()
                    else:
                        search_input.press("Enter")

                    page.wait_for_timeout(4000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_term)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("pr.salud", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> PrSaludResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        facility_name = ""
        facility_type = ""
        license_number = ""
        license_status = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if any(kw in lower for kw in ["nombre", "facilidad", "facility"]) and ":" in stripped and not facility_name:  # noqa: E501
                facility_name = stripped.split(":", 1)[1].strip()
            elif any(kw in lower for kw in ["tipo", "type", "clase"]) and ":" in stripped and not facility_type:  # noqa: E501
                facility_type = stripped.split(":", 1)[1].strip()
            elif any(kw in lower for kw in ["licencia", "license", "número"]) and ":" in stripped and not license_number:  # noqa: E501
                license_number = stripped.split(":", 1)[1].strip()
            elif "estado" in lower and ":" in stripped and not license_status:
                license_status = stripped.split(":", 1)[1].strip()

        return PrSaludResult(
            queried_at=datetime.now(),
            search_term=search_term,
            facility_name=facility_name,
            facility_type=facility_type,
            license_number=license_number,
            license_status=license_status,
            details=body_text.strip()[:500],
        )
