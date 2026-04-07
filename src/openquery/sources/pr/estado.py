"""Estado source — Puerto Rico Department of State business filings.

Queries the PR Department of State corporate filing system for business
registration status.

Source: https://prcorpfiling.f1hst.com/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pr.estado import PrEstadoResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

ESTADO_URL = "https://prcorpfiling.f1hst.com/"


@register
class PrEstadoSource(BaseSource):
    """Query Puerto Rico Department of State business filings by name."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pr.estado",
            display_name="Estado PR — Registro de Corporaciones",
            description=(
                "Puerto Rico Department of State: business filing and corporate registration by name"  # noqa: E501
            ),
            country="PR",
            url=ESTADO_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("name", "") or input.document_number.strip()
        if not search_term:
            raise SourceError("pr.estado", "Business name is required")
        return self._query(search_term=search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> PrEstadoResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("pr.estado", "name", search_term)

        with browser.page(ESTADO_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "page_loaded")

                search_input = page.query_selector(
                    'input[name*="name"], input[id*="name"], '
                    'input[name*="search"], input[type="search"], '
                    'input[type="text"], input[placeholder*="name"]'
                )
                if search_input:
                    search_input.fill(search_term)
                    logger.info("Querying PR Estado for business: %s", search_term)

                    submit_btn = page.query_selector(
                        'button[type="submit"], input[type="submit"], '
                        'button:has-text("Search"), input[value*="Search"]'
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
                raise SourceError("pr.estado", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> PrEstadoResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        entity_name = ""
        entity_type = ""
        registration_number = ""
        status = ""
        registration_date = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if any(kw in lower for kw in ["entity name", "corporation name", "nombre"]) and ":" in stripped and not entity_name:  # noqa: E501
                entity_name = stripped.split(":", 1)[1].strip()
            elif any(kw in lower for kw in ["entity type", "type", "tipo"]) and ":" in stripped and not entity_type:  # noqa: E501
                entity_type = stripped.split(":", 1)[1].strip()
            elif any(kw in lower for kw in ["charter", "registration", "número"]) and ":" in stripped and not registration_number:  # noqa: E501
                registration_number = stripped.split(":", 1)[1].strip()
            elif "status" in lower and ":" in stripped and not status:
                status = stripped.split(":", 1)[1].strip()
            elif any(kw in lower for kw in ["date", "fecha"]) and ":" in stripped and not registration_date:  # noqa: E501
                registration_date = stripped.split(":", 1)[1].strip()

        return PrEstadoResult(
            queried_at=datetime.now(),
            search_term=search_term,
            entity_name=entity_name,
            entity_type=entity_type,
            registration_number=registration_number,
            status=status,
            registration_date=registration_date,
            details=body_text.strip()[:500],
        )
