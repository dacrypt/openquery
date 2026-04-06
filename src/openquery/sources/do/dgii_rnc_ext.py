"""DGII RNC extended source — Dominican Republic company registry.

Queries DGII's RNC portal for extended company information including
status, economic activity, and address by RNC number.

Source: https://dgii.gov.do/app/WebApps/ConsultasWeb/consultas/rnc.aspx
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.do.dgii_rnc_ext import DgiiRncExtResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

DGII_RNC_EXT_URL = "https://dgii.gov.do/app/WebApps/ConsultasWeb/consultas/rnc.aspx"


@register
class DgiiRncExtSource(BaseSource):
    """Query Dominican Republic DGII RNC extended company information."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="do.dgii_rnc_ext",
            display_name="DGII — RNC Información Extendida",
            description=(
                "Dominican Republic DGII RNC extended: company info, status, economic activity, address by RNC"  # noqa: E501
            ),
            country="DO",
            url=DGII_RNC_EXT_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        rnc = input.extra.get("rnc", "") or input.document_number.strip()
        if not rnc:
            raise SourceError("do.dgii_rnc_ext", "RNC is required")
        return self._query(rnc=rnc, audit=input.audit)

    def _query(self, rnc: str, audit: bool = False) -> DgiiRncExtResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("do.dgii_rnc_ext", "rnc", rnc)

        with browser.page(DGII_RNC_EXT_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "page_loaded")

                rnc_input = page.query_selector(
                    '#txtRNC, input[name="txtRNC"], '
                    'input[name*="rnc"], input[id*="rnc"], '
                    'input[placeholder*="RNC"], input[type="text"]'
                )
                if not rnc_input:
                    raise SourceError("do.dgii_rnc_ext", "Could not find RNC input field")

                rnc_input.fill(rnc)
                logger.info("Querying DGII RNC extended for: %s", rnc)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit_btn = page.query_selector(
                    '#btnBuscar, input[name="btnBuscar"], '
                    'input[type="submit"], button[type="submit"], '
                    'button:has-text("Buscar"), input[value*="Buscar"]'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    rnc_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, rnc)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("do.dgii_rnc_ext", f"Query failed: {e}") from e

    def _parse_result(self, page, rnc: str) -> DgiiRncExtResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        company_name = ""
        commercial_name = ""
        status = ""
        economic_activity = ""
        address = ""

        field_map = {
            "nombre o razón social": "company_name",
            "razón social": "company_name",
            "razon social": "company_name",
            "nombre comercial": "commercial_name",
            "estado": "status",
            "estatus": "status",
            "actividad económica": "economic_activity",
            "actividad economica": "economic_activity",
            "dirección": "address",
            "direccion": "address",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_map.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value:
                        if field == "company_name" and not company_name:
                            company_name = value
                        elif field == "commercial_name" and not commercial_name:
                            commercial_name = value
                        elif field == "status" and not status:
                            status = value
                        elif field == "economic_activity" and not economic_activity:
                            economic_activity = value
                        elif field == "address" and not address:
                            address = value
                    break

        return DgiiRncExtResult(
            queried_at=datetime.now(),
            rnc=rnc,
            company_name=company_name,
            commercial_name=commercial_name,
            status=status,
            economic_activity=economic_activity,
            address=address,
            details=body_text.strip()[:500],
        )
