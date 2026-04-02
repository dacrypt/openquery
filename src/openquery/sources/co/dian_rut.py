"""DIAN RUT source — Colombian tax registry status.

Queries the DIAN MUISCA portal for RUT (Registro Único Tributario) status.

Flow:
1. Navigate to the DIAN RUT consultation page
2. Select document type and enter document number
3. Submit and parse result

Source: https://muisca.dian.gov.co/WebRutMuisca/DefConsultaEstadoRUT.faces
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.dian_rut import DianRutResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

DIAN_RUT_URL = "https://muisca.dian.gov.co/WebRutMuisca/DefConsultaEstadoRUT.faces"


@register
class DianRutSource(BaseSource):
    """Query DIAN RUT status (Colombian tax registry)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.dian_rut",
            display_name="DIAN — Estado del RUT",
            description="Colombian RUT (Registro Único Tributario) status from DIAN MUISCA",
            country="CO",
            url=DIAN_RUT_URL,
            supported_inputs=[DocumentType.CEDULA, DocumentType.NIT],
            requires_captcha=True,  # Cloudflare Turnstile
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type not in (DocumentType.CEDULA, DocumentType.NIT):
            raise SourceError(
                "co.dian_rut",
                f"Unsupported document type: {input.document_type}. Use cedula or NIT.",
            )
        return self._query(input.document_number, input.document_type, audit=input.audit)

    def _query(self, documento: str, doc_type: DocumentType, audit: bool = False) -> DianRutResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.dian_rut", doc_type.value, documento)

        with browser.page(DIAN_RUT_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Select document type
                doc_type_value = "Nit" if doc_type == DocumentType.NIT else "Cc"
                doc_select = page.query_selector(
                    'select[id*="tipo"], select[name*="tipo"]'
                )
                if doc_select:
                    page.select_option(
                        'select[id*="tipo"], select[name*="tipo"]',
                        label=doc_type_value,
                        timeout=5000,
                    )

                # Fill document number
                doc_input = page.query_selector(
                    'input[type="text"][id*="numero"], '
                    'input[type="text"][id*="nit"], '
                    'input[type="text"]'
                )
                if not doc_input:
                    raise SourceError("co.dian_rut", "Could not find document input field")

                doc_input.fill(documento)
                logger.info("Filled document: %s", documento)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit_btn = page.query_selector(
                    'input[type="submit"], button[type="submit"], '
                    'input[id*="buscar"], input[id*="consultar"], '
                    'button[id*="buscar"], button[id*="consultar"]'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    doc_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, documento, doc_type)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("co.dian_rut", f"Query failed: {e}") from e

    def _parse_result(self, page, documento: str, doc_type: DocumentType) -> DianRutResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        result = DianRutResult(
            queried_at=datetime.now(),
            documento=documento,
            tipo_documento=doc_type.value,
        )

        # Extract fields from result page
        field_map = {
            "razón social": "nombre_razon_social",
            "razon social": "nombre_razon_social",
            "nombre": "nombre_razon_social",
            "estado": "estado_rut",
            "nit": "nit",
            "actividad económica": "actividad_economica",
            "actividad economica": "actividad_economica",
            "dirección": "direccion",
            "direccion": "direccion",
            "municipio": "municipio",
            "departamento": "departamento",
            "fecha de inscripción": "fecha_inscripcion",
        }

        for line in body_text.split("\n"):
            line_stripped = line.strip()
            line_lower = line_stripped.lower()
            for label, field in field_map.items():
                if label in line_lower:
                    parts = line_stripped.split(":")
                    if len(parts) > 1:
                        value = ":".join(parts[1:]).strip()
                        setattr(result, field, value)
                        break

        return result
