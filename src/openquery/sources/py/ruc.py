"""Paraguay RUC source — SET/DNIT tax registry.

Queries Paraguay's Subsecretaría de Estado de Tributación (SET) for
RUC (Registro Único de Contribuyentes) data.

Source: https://servicios.set.gov.py/eset-publico/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.py.ruc import PyRucResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SET_URL = "https://servicios.set.gov.py/eset-publico/perfilPublicoContribIService.do"


@register
class PyRucSource(BaseSource):
    """Query Paraguayan tax registry (SET/DNIT) by RUC."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="py.ruc",
            display_name="SET — Consulta RUC",
            description="Paraguayan tax registry: business name, status, economic activity (SET/DNIT)",
            country="PY",
            url=SET_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=True,  # reCAPTCHA v2
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        ruc = input.extra.get("ruc", "") or input.document_number
        if not ruc:
            raise SourceError("py.ruc", "RUC is required")
        return self._query(ruc.strip(), audit=input.audit)

    def _query(self, ruc: str, audit: bool = False) -> PyRucResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("py.ruc", "ruc", ruc)

        with browser.page(SET_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill RUC — exact selector: input[name="ruc"]
                ruc_input = page.query_selector(
                    'input[name="ruc"], #ruc'
                )
                if not ruc_input:
                    raise SourceError("py.ruc", "Could not find RUC input field")

                ruc_input.fill(ruc)
                logger.info("Filled RUC: %s", ruc)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Solve reCAPTCHA if present
                from openquery.core.captcha_middleware import solve_page_captchas
                solve_page_captchas(page)

                # Submit — exact selector: button[name="btnBuscar"]
                submit = page.query_selector(
                    'button[name="btnBuscar"], '
                    'button[type="submit"]'
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
                raise SourceError("py.ruc", f"Query failed: {e}") from e

    def _parse_result(self, page, ruc: str) -> PyRucResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        result = PyRucResult(queried_at=datetime.now(), ruc=ruc)

        field_map = {
            "razon social": "razon_social",
            "nombre fantasia": "nombre_fantasia",
            "estado": "estado",
            "tipo": "tipo_contribuyente",
            "actividad": "actividad_economica",
            "direccion": "direccion",
            "departamento": "departamento",
            "distrito": "distrito",
            "telefono": "telefono",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_map.items():
                if label in lower and (":" in stripped or "\t" in stripped):
                    sep = ":" if ":" in stripped else "\t"
                    value = stripped.split(sep, 1)[1].strip()
                    setattr(result, field, value)
                    break

        return result
