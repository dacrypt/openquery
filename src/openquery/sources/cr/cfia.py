"""CFIA source — Costa Rica engineer/architect professional registry.

Queries the Colegio Federado de Ingenieros y Arquitectos (CFIA) for
professional registration status.

Source: https://www.cfia.or.cr/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.cr.cfia import CfiaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CFIA_URL = "https://www.cfia.or.cr/"


@register
class CfiaSource(BaseSource):
    """Query Costa Rica CFIA professional registry by name or license."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="cr.cfia",
            display_name="CFIA — Registro Profesional",
            description=(
                "Costa Rica CFIA: engineer and architect professional registry by name or license"
            ),
            country="CR",
            url=CFIA_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("search_term", "") or input.document_number.strip()
        if not search_term:
            raise SourceError("cr.cfia", "Name or license number is required")
        return self._query(search_term=search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> CfiaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("cr.cfia", "search_term", search_term)

        with browser.page(CFIA_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "page_loaded")

                search_input = page.query_selector(
                    'input[name*="nombre"], input[id*="nombre"], '
                    'input[name*="search"], input[type="search"], '
                    'input[type="text"], input[placeholder*="nombre"]'
                )
                if search_input:
                    search_input.fill(search_term)
                    logger.info("Querying CFIA for: %s", search_term)

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
                raise SourceError("cr.cfia", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> CfiaResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        professional_name = ""
        license_number = ""
        profession = ""
        membership_status = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if "nombre" in lower and ":" in stripped and not professional_name:
                professional_name = stripped.split(":", 1)[1].strip()
            elif any(kw in lower for kw in ["carnet", "cédula", "número"]) and ":" in stripped and not license_number:  # noqa: E501
                license_number = stripped.split(":", 1)[1].strip()
            elif any(kw in lower for kw in ["especialidad", "profesión", "ingeniería", "arquitectura"]) and ":" in stripped and not profession:  # noqa: E501
                profession = stripped.split(":", 1)[1].strip()
            elif "estado" in lower and ":" in stripped and not membership_status:
                membership_status = stripped.split(":", 1)[1].strip()

        return CfiaResult(
            queried_at=datetime.now(),
            search_term=search_term,
            professional_name=professional_name,
            license_number=license_number,
            profession=profession,
            membership_status=membership_status,
            details=body_text.strip()[:500],
        )
