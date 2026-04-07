"""SENACSA source — Paraguay animal health registry.

Queries the Servicio Nacional de Calidad y Salud Animal (SENACSA) for
farm sanitary registry status.

Source: https://www.senacsa.gov.py/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.py.senacsa import SenácsaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SENACSA_URL = "https://www.senacsa.gov.py/"


@register
class SenácsaSource(BaseSource):
    """Query Paraguay SENACSA animal health registry by farm name."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="py.senacsa",
            display_name="SENACSA — Registro Sanitario Animal",
            description=(
                "Paraguay SENACSA: animal health sanitary registry by farm name"
            ),
            country="PY",
            url=SENACSA_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("farm_name", "") or input.document_number.strip()
        if not search_term:
            raise SourceError("py.senacsa", "Farm name is required")
        return self._query(search_term=search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> SenácsaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("py.senacsa", "farm_name", search_term)

        with browser.page(SENACSA_URL) as page:
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
                    logger.info("Querying SENACSA for farm: %s", search_term)

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
                raise SourceError("py.senacsa", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> SenácsaResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        farm_name = ""
        owner_name = ""
        sanitary_status = ""
        registration_number = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if any(kw in lower for kw in ["establecimiento", "nombre establecimiento"]) and ":" in stripped and not farm_name:  # noqa: E501
                farm_name = stripped.split(":", 1)[1].strip()
            elif any(kw in lower for kw in ["propietario", "titular"]) and ":" in stripped and not owner_name:  # noqa: E501
                owner_name = stripped.split(":", 1)[1].strip()
            elif any(kw in lower for kw in ["estado sanitario", "estado"]) and ":" in stripped and not sanitary_status:  # noqa: E501
                sanitary_status = stripped.split(":", 1)[1].strip()
            elif any(kw in lower for kw in ["registro", "número"]) and ":" in stripped and not registration_number:  # noqa: E501
                registration_number = stripped.split(":", 1)[1].strip()

        return SenácsaResult(
            queried_at=datetime.now(),
            search_term=search_term,
            farm_name=farm_name,
            owner_name=owner_name,
            sanitary_status=sanitary_status,
            registration_number=registration_number,
            details=body_text.strip()[:500],
        )
