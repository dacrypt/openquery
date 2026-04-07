"""MTSS source — Uruguay ministry of labor employer data.

Queries the Ministerio de Trabajo y Seguridad Social (MTSS) of Uruguay
for employer labor compliance data.

Source: https://www.gub.uy/ministerio-trabajo-seguridad-social/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.uy.mtss import MtssResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

MTSS_URL = "https://www.gub.uy/ministerio-trabajo-seguridad-social/"


@register
class MtssSource(BaseSource):
    """Query Uruguay MTSS labor ministry employer data by employer name."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="uy.mtss",
            display_name="MTSS — Datos Laborales",
            description=(
                "Uruguay MTSS: labor ministry employer compliance data by employer name"
            ),
            country="UY",
            url=MTSS_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("employer", "") or input.document_number.strip()
        if not search_term:
            raise SourceError("uy.mtss", "Employer name is required")
        return self._query(search_term=search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> MtssResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("uy.mtss", "employer", search_term)

        with browser.page(MTSS_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "page_loaded")

                search_input = page.query_selector(
                    'input[name*="empleador"], input[id*="empleador"], '
                    'input[type="search"], input[type="text"], '
                    'input[name*="search"], input[placeholder*="empresa"]'
                )
                if search_input:
                    search_input.fill(search_term)
                    logger.info("Querying MTSS for employer: %s", search_term)

                    submit_btn = page.query_selector(
                        'button[type="submit"], input[type="submit"], '
                        'button:has-text("Buscar"), button:has-text("Consultar")'
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
                raise SourceError("uy.mtss", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> MtssResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        employer_name = ""
        compliance_status = ""
        industry = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if any(kw in lower for kw in ["empleador", "empresa", "nombre"]) and ":" in stripped and not employer_name:  # noqa: E501
                employer_name = stripped.split(":", 1)[1].strip()
            elif any(kw in lower for kw in ["cumplimiento", "estado"]) and ":" in stripped and not compliance_status:  # noqa: E501
                compliance_status = stripped.split(":", 1)[1].strip()
            elif any(kw in lower for kw in ["industria", "sector", "actividad"]) and ":" in stripped and not industry:  # noqa: E501
                industry = stripped.split(":", 1)[1].strip()

        return MtssResult(
            queried_at=datetime.now(),
            search_term=search_term,
            employer_name=employer_name,
            compliance_status=compliance_status,
            industry=industry,
            details=body_text.strip()[:500],
        )
