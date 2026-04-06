"""Nicaragua DGI source — tax/RUC registry lookup.

Queries the DGI (Dirección General de Ingresos) portal for taxpayer info.
Browser-based, public, no authentication required.

Source: https://dgienlinea.dgi.gob.ni/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ni.dgi import NiDgiResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

DGI_URL = "https://dgienlinea.dgi.gob.ni/"


@register
class NiDgiSource(BaseSource):
    """Query Nicaragua DGI tax registry by RUC number."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ni.dgi",
            display_name="DGI — Consulta de Contribuyentes",
            description=(
                "Nicaragua DGI taxpayer lookup: name, status, fiscal address, "
                "and economic activity (Dirección General de Ingresos)"
            ),
            country="NI",
            url=DGI_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        ruc = input.extra.get("ruc", "") or input.document_number
        if not ruc:
            raise SourceError("ni.dgi", "RUC is required")
        return self._query(ruc.strip(), audit=input.audit)

    def _query(self, ruc: str, audit: bool = False) -> NiDgiResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("ni.dgi", "ruc", ruc)

        with browser.page(DGI_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                ruc_input = page.query_selector(
                    '#txtRuc, input[name="txtRuc"], '
                    '#ruc, input[name="ruc"], '
                    'input[placeholder*="RUC"], input[placeholder*="ruc"]'
                )
                if not ruc_input:
                    raise SourceError("ni.dgi", "Could not find RUC input field")

                ruc_input.fill(ruc)
                logger.info("Filled RUC: %s", ruc)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    '#btnBuscar, input[name="btnBuscar"], '
                    '#btnConsultar, input[name="btnConsultar"], '
                    'button[type="submit"]'
                )
                if submit:
                    submit.click()
                else:
                    ruc_input.press("Enter")

                page.wait_for_timeout(3000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, ruc)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("ni.dgi", f"Query failed: {e}") from e

    def _parse_result(self, page, ruc: str) -> NiDgiResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = NiDgiResult(queried_at=datetime.now(), ruc=ruc)

        field_map = {
            "nombre": "taxpayer_name",
            "razón social": "taxpayer_name",
            "razon social": "taxpayer_name",
            "estado": "tax_status",
            "dirección": "address",
            "direccion": "address",
            "actividad": "economic_activity",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_map.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value:
                        setattr(result, field, value)
                    break

        result.details = {"raw": body_text.strip()[:500]}

        return result
