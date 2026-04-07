"""MARN source — El Salvador environmental permits.

Queries the Ministerio de Medio Ambiente y Recursos Naturales (MARN) of
El Salvador for environmental permit status.

Source: https://www.marn.gob.sv/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.sv.marn import MarnResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

MARN_URL = "https://www.marn.gob.sv/"


@register
class MarnSource(BaseSource):
    """Query El Salvador MARN environmental permits by company name."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="sv.marn",
            display_name="MARN — Permisos Ambientales",
            description=(
                "El Salvador MARN: environmental permit status by company name"
            ),
            country="SV",
            url=MARN_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("company_name", "") or input.document_number.strip()
        if not search_term:
            raise SourceError("sv.marn", "Company name is required")
        return self._query(search_term=search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> MarnResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("sv.marn", "company_name", search_term)

        with browser.page(MARN_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "page_loaded")

                search_input = page.query_selector(
                    'input[name*="empresa"], input[id*="empresa"], '
                    'input[type="search"], input[type="text"], '
                    'input[name*="search"], input[placeholder*="empresa"]'
                )
                if search_input:
                    search_input.fill(search_term)
                    logger.info("Querying MARN for company: %s", search_term)

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
                raise SourceError("sv.marn", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> MarnResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        company_name = ""
        permit_number = ""
        permit_type = ""
        permit_status = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if any(kw in lower for kw in ["empresa", "nombre", "titular"]) and ":" in stripped and not company_name:  # noqa: E501
                company_name = stripped.split(":", 1)[1].strip()
            elif any(kw in lower for kw in ["permiso", "número", "resolución"]) and ":" in stripped and not permit_number:  # noqa: E501
                permit_number = stripped.split(":", 1)[1].strip()
            elif any(kw in lower for kw in ["tipo", "categoría", "clase"]) and ":" in stripped and not permit_type:  # noqa: E501
                permit_type = stripped.split(":", 1)[1].strip()
            elif "estado" in lower and ":" in stripped and not permit_status:
                permit_status = stripped.split(":", 1)[1].strip()

        return MarnResult(
            queried_at=datetime.now(),
            search_term=search_term,
            company_name=company_name,
            permit_number=permit_number,
            permit_type=permit_type,
            permit_status=permit_status,
            details=body_text.strip()[:500],
        )
