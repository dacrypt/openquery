"""Dominican Republic RNC source — DGII tax registry.

Queries the Dirección General de Impuestos Internos (DGII) for taxpayer
registration data by RNC or cedula.

Source: https://dgii.gov.do/herramientas/consultas/Paginas/RNC.aspx
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.do.rnc import DoRncResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

DGII_URL = "https://dgii.gov.do/herramientas/consultas/Paginas/RNC.aspx"


@register
class DoRncSource(BaseSource):
    """Query Dominican Republic DGII tax registry by RNC/cedula."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="do.rnc",
            display_name="DGII — Consulta RNC",
            description="Dominican Republic tax registry: taxpayer name, status, economic activity (DGII)",  # noqa: E501
            country="DO",
            url=DGII_URL,
            supported_inputs=[DocumentType.CEDULA, DocumentType.NIT, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        rnc = input.extra.get("rnc", "") or input.document_number
        if not rnc:
            raise SourceError("do.rnc", "RNC or cédula is required")
        return self._query(rnc.strip(), audit=input.audit)

    def _query(self, rnc: str, audit: bool = False) -> DoRncResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("do.rnc", "rnc", rnc)

        with browser.page(DGII_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill RNC/cedula
                rnc_input = page.query_selector(
                    "#ctl00_SPWebPartManager1_g_baborrnc_txtRNCCedula, "
                    'input[id*="txtRNC"], input[id*="txtCedula"], '
                    'input[type="text"]'
                )
                if not rnc_input:
                    raise SourceError("do.rnc", "Could not find RNC input field")

                rnc_input.fill(rnc)
                logger.info("Filled RNC: %s", rnc)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    "#ctl00_SPWebPartManager1_g_baborrnc_btnBuscar, "
                    'input[id*="btnBuscar"], '
                    'button[type="submit"], input[type="submit"]'
                )
                if submit:
                    submit.click()
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
                raise SourceError("do.rnc", f"Query failed: {e}") from e

    def _parse_result(self, page, rnc: str) -> DoRncResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        result = DoRncResult(queried_at=datetime.now(), rnc=rnc)

        field_map = {
            "nombre": "nombre",
            "nombre comercial": "nombre_comercial",
            "categoria": "categoria",
            "regimen de pagos": "regimen_pagos",
            "estado": "estado",
            "actividad economica": "actividad_economica",
            "administracion local": "administracion_local",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_map.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    setattr(result, field, value)
                    break

        return result
