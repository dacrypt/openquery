"""IGSS source — Guatemala social security affiliation lookup.

Queries the Instituto Guatemalteco de Seguridad Social (IGSS) for
affiliation status.

Source: https://www.igss.gob.gt/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.gt.igss import IgssResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

IGSS_URL = "https://www.igss.gob.gt/"


@register
class IgssSource(BaseSource):
    """Query Guatemala IGSS social security by affiliation number."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="gt.igss",
            display_name="IGSS — Afiliación al Seguro Social",
            description=(
                "Guatemala IGSS: social security affiliation status by affiliation number"
            ),
            country="GT",
            url=IGSS_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        affiliation_number = input.extra.get("affiliation_number", "") or input.document_number.strip()  # noqa: E501
        if not affiliation_number:
            raise SourceError("gt.igss", "Affiliation number is required")
        return self._query(affiliation_number=affiliation_number, audit=input.audit)

    def _query(self, affiliation_number: str, audit: bool = False) -> IgssResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("gt.igss", "affiliation_number", affiliation_number)

        with browser.page(IGSS_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "page_loaded")

                search_input = page.query_selector(
                    'input[name*="afiliado"], input[id*="afiliado"], '
                    'input[name*="numero"], input[type="text"], '
                    'input[name*="seguro"], input[type="search"]'
                )
                if search_input:
                    search_input.fill(affiliation_number)
                    logger.info("Querying IGSS for affiliation: %s", affiliation_number)

                    submit_btn = page.query_selector(
                        'button[type="submit"], input[type="submit"], '
                        'button:has-text("Consultar"), button:has-text("Buscar")'
                    )
                    if submit_btn:
                        submit_btn.click()
                    else:
                        search_input.press("Enter")

                    page.wait_for_timeout(4000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, affiliation_number)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("gt.igss", f"Query failed: {e}") from e

    def _parse_result(self, page, affiliation_number: str) -> IgssResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        affiliate_name = ""
        affiliation_status = ""
        employer = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if "nombre" in lower and ":" in stripped and not affiliate_name:
                affiliate_name = stripped.split(":", 1)[1].strip()
            elif "estado" in lower and ":" in stripped and not affiliation_status:
                affiliation_status = stripped.split(":", 1)[1].strip()
            elif any(kw in lower for kw in ["patrono", "empleador", "empresa"]) and ":" in stripped and not employer:  # noqa: E501
                employer = stripped.split(":", 1)[1].strip()

        return IgssResult(
            queried_at=datetime.now(),
            affiliation_number=affiliation_number,
            affiliate_name=affiliate_name,
            affiliation_status=affiliation_status,
            employer=employer,
            details=body_text.strip()[:500],
        )
