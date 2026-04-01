"""Cambio de Estrato source — Colombian socioeconomic stratum certification.

Queries a municipal government portal for socioeconomic stratum (estrato)
certification by cedula number.

Flow:
1. Navigate to the municipal consultation page
2. Enter cedula number
3. Submit and parse stratum result

Source: https://www.bucaramanga.gov.co/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.cambio_estrato import CambioEstratoResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

ESTRATO_URL = "https://www.bucaramanga.gov.co/"


@register
class CambioEstratoSource(BaseSource):
    """Query Colombian socioeconomic stratum certification."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.cambio_estrato",
            display_name="Estratificaci\u00f3n \u2014 Certificado de Estrato",
            description="Colombian socioeconomic stratum certification",
            country="CO",
            url=ESTRATO_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CEDULA:
            raise SourceError(
                "co.cambio_estrato",
                f"Unsupported document type: {input.document_type}. Use cedula.",
            )
        return self._query(input.document_number, audit=input.audit)

    def _query(self, documento: str, audit: bool = False) -> CambioEstratoResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.cambio_estrato", "cedula", documento)

        with browser.page(ESTRATO_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_selector('input[type="text"]', timeout=15000)
                page.wait_for_timeout(2000)

                # Fill cedula number
                doc_input = page.query_selector(
                    'input[type="text"][id*="cedula"], '
                    'input[type="text"][id*="documento"], '
                    'input[type="text"][id*="numero"], '
                    'input[type="text"]'
                )
                if not doc_input:
                    raise SourceError("co.cambio_estrato", "Could not find document input field")

                doc_input.fill(documento)
                logger.info("Filled cedula: %s", documento)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="consultar"], button[id*="buscar"], '
                    'input[id*="consultar"], input[id*="buscar"]'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    doc_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, documento)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("co.cambio_estrato", f"Query failed: {e}") from e

    def _parse_result(self, page, documento: str) -> CambioEstratoResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        result = CambioEstratoResult(
            queried_at=datetime.now(),
            cedula=documento,
        )

        field_map = {
            "estrato": "estrato",
            "direcci\u00f3n": "direccion",
            "direccion": "direccion",
            "municipio": "municipio",
            "departamento": "departamento",
            "nombre": "nombre",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_map.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    setattr(result, field, value)
                    break

        # Validate estrato is within expected range
        if result.estrato and result.estrato.strip() in ("1", "2", "3", "4", "5", "6"):
            result.mensaje = f"Estrato {result.estrato}"
        elif "no se encontr" in body_text.lower():
            result.mensaje = "No se encontr\u00f3 registro de estrato"
        elif result.estrato:
            result.mensaje = f"Estrato reportado: {result.estrato}"

        return result
