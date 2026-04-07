"""IHTT source — Honduras tourism establishment registry.

Queries the Instituto Hondureño de Turismo (IHT) for tourism establishment
license status.

Source: https://www.iht.hn/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.hn.ihtt import IhttResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

IHTT_URL = "https://www.iht.hn/"


@register
class IhttSource(BaseSource):
    """Query Honduras IHT tourism establishment registry by name."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="hn.ihtt",
            display_name="IHT — Registro de Establecimientos Turísticos",
            description=(
                "Honduras IHT: tourism establishment license status by establishment name"
            ),
            country="HN",
            url=IHTT_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("establishment_name", "") or input.document_number.strip()
        if not search_term:
            raise SourceError("hn.ihtt", "Establishment name is required")
        return self._query(search_term=search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> IhttResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("hn.ihtt", "establishment_name", search_term)

        with browser.page(IHTT_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "page_loaded")

                search_input = page.query_selector(
                    'input[name*="establecimiento"], input[id*="establecimiento"], '
                    'input[type="search"], input[type="text"], '
                    'input[name*="search"], input[placeholder*="nombre"]'
                )
                if search_input:
                    search_input.fill(search_term)
                    logger.info("Querying IHT for establishment: %s", search_term)

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

                result = self._parse_result(page, search_term)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("hn.ihtt", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> IhttResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        establishment_name = ""
        establishment_type = ""
        license_number = ""
        license_status = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if "nombre" in lower and ":" in stripped and not establishment_name:
                establishment_name = stripped.split(":", 1)[1].strip()
            elif any(kw in lower for kw in ["tipo", "clase", "categoría"]) and ":" in stripped and not establishment_type:  # noqa: E501
                establishment_type = stripped.split(":", 1)[1].strip()
            elif any(kw in lower for kw in ["licencia", "registro", "número"]) and ":" in stripped and not license_number:  # noqa: E501
                license_number = stripped.split(":", 1)[1].strip()
            elif "estado" in lower and ":" in stripped and not license_status:
                license_status = stripped.split(":", 1)[1].strip()

        return IhttResult(
            queried_at=datetime.now(),
            search_term=search_term,
            establishment_name=establishment_name,
            establishment_type=establishment_type,
            license_number=license_number,
            license_status=license_status,
            details=body_text.strip()[:500],
        )
