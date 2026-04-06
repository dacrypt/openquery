"""Bolivia NIT source — SIN (Servicio de Impuestos Nacionales) tax registry.

Queries Bolivia's SIN for NIT (Número de Identificación Tributaria) data.

Source: https://ov.impuestos.gob.bo/paginas/publico/consultaspublicas.aspx
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.bo.nit import BoNitResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SIN_URL = "https://ov.impuestos.gob.bo/paginas/publico/consultaspublicas.aspx"


@register
class BoNitSource(BaseSource):
    """Query Bolivian tax registry (SIN) by NIT."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="bo.nit",
            display_name="SIN — Consulta NIT",
            description="Bolivian tax registry: taxpayer name, status (Servicio de Impuestos Nacionales)",  # noqa: E501
            country="BO",
            url=SIN_URL,
            supported_inputs=[DocumentType.NIT, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        nit = input.extra.get("nit", "") or input.document_number
        if not nit:
            raise SourceError("bo.nit", "NIT is required")
        return self._query(nit.strip(), audit=input.audit)

    def _query(self, nit: str, audit: bool = False) -> BoNitResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("bo.nit", "nit", nit)

        with browser.page(SIN_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                nit_input = page.query_selector(
                    '#txtNIT, input[name*="NIT"], input[name*="nit"], '
                    'input[id*="nit"], input[type="text"]'
                )
                if not nit_input:
                    raise SourceError("bo.nit", "Could not find NIT input field")

                nit_input.fill(nit)
                logger.info("Filled NIT: %s", nit)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'input[type="submit"], button[type="submit"], '
                    'button:has-text("Consultar"), button:has-text("Verificar")'
                )
                if submit:
                    submit.click()
                else:
                    nit_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, nit)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("bo.nit", f"Query failed: {e}") from e

    def _parse_result(self, page, nit: str) -> BoNitResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        result = BoNitResult(queried_at=datetime.now(), nit=nit)

        field_map = {
            "razon social": "razon_social",
            "nombre": "razon_social",
            "estado": "estado",
            "tipo": "tipo_contribuyente",
            "actividad": "actividad_economica",
            "domicilio": "domicilio_fiscal",
            "departamento": "departamento",
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
