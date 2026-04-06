"""SIGET source — El Salvador utilities regulator lookup.

Queries El Salvador's SIGET (Superintendencia General de Electricidad y
Telecomunicaciones) for authorized providers and service type by company name.

Source: https://www.siget.gob.sv/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.sv.siget import SigetResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SIGET_URL = "https://www.siget.gob.sv/"


@register
class SigetSource(BaseSource):
    """Query El Salvador SIGET authorized utility providers by company name."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="sv.siget",
            display_name="SIGET — Proveedores Autorizados",
            description=(
                "El Salvador SIGET utilities regulator: authorized providers and service type by company name"  # noqa: E501
            ),
            country="SV",
            url=SIGET_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (
            input.extra.get("company_name", "") or input.document_number.strip()
        )
        if not search_term:
            raise SourceError("sv.siget", "Company name is required")
        return self._query(search_term=search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> SigetResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("sv.siget", "search_term", search_term)

        with browser.page(SIGET_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "page_loaded")

                search_input = page.query_selector(
                    'input[name*="proveedor"], input[name*="search"], '
                    'input[id*="proveedor"], input[id*="search"], '
                    'input[placeholder*="proveedor"], input[placeholder*="empresa"], '
                    'input[type="search"], input[type="text"]'
                )
                if not search_input:
                    raise SourceError("sv.siget", "Could not find search input field")

                search_input.fill(search_term)
                logger.info("Querying SIGET for provider: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit_btn = page.query_selector(
                    'input[type="submit"], button[type="submit"], '
                    'button:has-text("Consultar"), button:has-text("Buscar"), '
                    'input[value*="Consultar"], input[value*="Buscar"]'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    search_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_term)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("sv.siget", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> SigetResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        provider_name = ""
        service_type = ""
        authorization_status = ""

        field_map = {
            "proveedor": "provider_name",
            "empresa": "provider_name",
            "nombre": "provider_name",
            "servicio": "service_type",
            "tipo": "service_type",
            "autorización": "authorization_status",
            "autorizacion": "authorization_status",
            "estado": "authorization_status",
            "licencia": "authorization_status",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_map.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value:
                        if field == "provider_name" and not provider_name:
                            provider_name = value
                        elif field == "service_type" and not service_type:
                            service_type = value
                        elif field == "authorization_status" and not authorization_status:
                            authorization_status = value
                    break

        return SigetResult(
            queried_at=datetime.now(),
            search_term=search_term,
            provider_name=provider_name,
            service_type=service_type,
            authorization_status=authorization_status,
            details=body_text.strip()[:500],
        )
