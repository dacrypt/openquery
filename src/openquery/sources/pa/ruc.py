"""Panama RUC source — DGI (Dirección General de Ingresos) tax registry.

Queries Panama's DGI for RUC (Registro Único de Contribuyentes) data.

Source: https://dgi.mef.gob.pa/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pa.ruc import PaRucResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

DGI_URL = "https://dgi.mef.gob.pa/Consultas/ConsultaRUC.aspx"


@register
class PaRucSource(BaseSource):
    """Query Panamanian tax registry (DGI) by RUC."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pa.ruc",
            display_name="DGI — Consulta RUC",
            description="Panamanian tax registry: taxpayer name, status (Dirección General de Ingresos)",
            country="PA",
            url=DGI_URL,
            supported_inputs=[DocumentType.NIT, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        ruc = input.extra.get("ruc", "") or input.document_number
        if not ruc:
            raise SourceError("pa.ruc", "RUC is required")
        return self._query(ruc.strip(), audit=input.audit)

    def _query(self, ruc: str, audit: bool = False) -> PaRucResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("pa.ruc", "ruc", ruc)

        with browser.page(DGI_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                ruc_input = page.query_selector(
                    '#txtRUC, input[name*="txtRUC"], input[id*="ruc"], '
                    'input[type="text"]'
                )
                if not ruc_input:
                    raise SourceError("pa.ruc", "Could not find RUC input field")

                ruc_input.fill(ruc)
                logger.info("Filled RUC: %s", ruc)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    '#btnConsultar, input[type="submit"], '
                    'button[type="submit"], '
                    'button:has-text("Consultar")'
                )
                if submit:
                    submit.click()
                else:
                    ruc_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, ruc)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("pa.ruc", f"Query failed: {e}") from e

    def _parse_result(self, page, ruc: str) -> PaRucResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        result = PaRucResult(queried_at=datetime.now(), ruc=ruc)

        field_map = {
            "nombre": "nombre",
            "razon social": "nombre",
            "dv": "dv",
            "estado": "estado",
            "tipo": "tipo_contribuyente",
            "actividad": "actividad_economica",
            "direccion": "direccion",
            "provincia": "provincia",
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
