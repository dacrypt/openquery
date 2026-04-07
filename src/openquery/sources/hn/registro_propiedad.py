"""Registro Propiedad source — Honduras property registry.

Queries the Instituto de la Propiedad (IP) of Honduras for property
ownership records.

Source: https://www.ip.gob.hn/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.hn.registro_propiedad import HnRegistroPropiedadResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

HN_REGISTRO_PROPIEDAD_URL = "https://www.ip.gob.hn/"


@register
class HnRegistroPropiedadSource(BaseSource):
    """Query Honduras property registry by property number."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="hn.registro_propiedad",
            display_name="IP Honduras — Registro de la Propiedad",
            description=(
                "Honduras Instituto de la Propiedad: property ownership registry by property number"
            ),
            country="HN",
            url=HN_REGISTRO_PROPIEDAD_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        property_number = input.extra.get("property_number", "") or input.document_number.strip()
        if not property_number:
            raise SourceError("hn.registro_propiedad", "Property number is required")
        return self._query(property_number=property_number, audit=input.audit)

    def _query(self, property_number: str, audit: bool = False) -> HnRegistroPropiedadResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("hn.registro_propiedad", "property_number", property_number)

        with browser.page(HN_REGISTRO_PROPIEDAD_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "page_loaded")

                search_input = page.query_selector(
                    'input[name*="propiedad"], input[id*="propiedad"], '
                    'input[name*="numero"], input[type="text"], '
                    'input[name*="predio"], input[type="search"]'
                )
                if search_input:
                    search_input.fill(property_number)
                    logger.info("Querying HN Registro Propiedad for: %s", property_number)

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

                result = self._parse_result(page, property_number)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("hn.registro_propiedad", f"Query failed: {e}") from e

    def _parse_result(self, page, property_number: str) -> HnRegistroPropiedadResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        owner_name = ""
        property_type = ""
        location = ""
        registration_date = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if any(kw in lower for kw in ["propietario", "dueño", "titular"]) and ":" in stripped and not owner_name:  # noqa: E501
                owner_name = stripped.split(":", 1)[1].strip()
            elif any(kw in lower for kw in ["tipo", "clase"]) and ":" in stripped and not property_type:  # noqa: E501
                property_type = stripped.split(":", 1)[1].strip()
            elif any(kw in lower for kw in ["ubicación", "municipio", "departamento"]) and ":" in stripped and not location:  # noqa: E501
                location = stripped.split(":", 1)[1].strip()
            elif any(kw in lower for kw in ["fecha", "inscripción"]) and ":" in stripped and not registration_date:  # noqa: E501
                registration_date = stripped.split(":", 1)[1].strip()

        return HnRegistroPropiedadResult(
            queried_at=datetime.now(),
            property_number=property_number,
            owner_name=owner_name,
            property_type=property_type,
            location=location,
            registration_date=registration_date,
            details=body_text.strip()[:500],
        )
