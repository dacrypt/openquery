"""SNR source — Colombian property registry (SuperNotariado).

Queries the Superintendencia de Notariado y Registro for property
ownership records by cédula or NIT.

Flow:
1. Navigate to SNR consultation page
2. Enter document number
3. Parse results table for property records

Source: https://radicacion.supernotariado.gov.co/app/consultaradicacion.html
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.snr import SnrPropiedad, SnrResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SNR_URL = "https://radicacion.supernotariado.gov.co/app/consultaradicacion.html"


@register
class SnrSource(BaseSource):
    """Query Colombian property registry (SNR / SuperNotariado)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.snr",
            display_name="SNR — Índice de Propietarios",
            description="Colombian property registry lookup (Superintendencia de Notariado y Registro)",
            country="CO",
            url=SNR_URL,
            supported_inputs=[DocumentType.CEDULA, DocumentType.NIT],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type not in (DocumentType.CEDULA, DocumentType.NIT):
            raise SourceError("co.snr", f"Only cedula/NIT supported, got: {input.document_type}")
        tipo = "nit" if input.document_type == DocumentType.NIT else "cedula"
        return self._query(input.document_number, tipo, audit=input.audit)

    def _query(self, documento: str, tipo: str = "cedula", audit: bool = False) -> SnrResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.snr", tipo, documento)

        with browser.page(SNR_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_selector('input[type="text"]', timeout=15000)
                page.wait_for_timeout(2000)

                # Select document type if dropdown exists
                tipo_select = page.query_selector(
                    'select[id*="tipo"], select[id*="document"], select[name*="tipo"]'
                )
                if tipo_select:
                    if tipo == "nit":
                        tipo_select.select_option(label="NIT")
                    else:
                        tipo_select.select_option(label="Cédula de Ciudadanía")

                # Fill document number
                doc_input = page.query_selector(
                    'input[type="text"][id*="documento"], '
                    'input[type="text"][id*="numero"], '
                    'input[type="text"][id*="cedula"], '
                    'input[type="text"]'
                )
                if not doc_input:
                    raise SourceError("co.snr", "Could not find document input field")

                doc_input.fill(documento)
                logger.info("Searching SNR for: %s", documento)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="consultar"], button[id*="buscar"]'
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
                raise SourceError("co.snr", f"Query failed: {e}") from e

    def _parse_result(self, page, documento: str) -> SnrResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        result = SnrResult(
            queried_at=datetime.now(),
            documento=documento,
        )

        # Extract name
        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if "nombre" in lower and ":" in stripped:
                result.nombre = stripped.split(":", 1)[1].strip()
                break

        # Try to extract property rows from tables
        rows = page.query_selector_all("table tr, .resultado, .item-resultado")

        propiedades = []
        for row in rows:
            text = row.inner_text()
            if not text.strip():
                continue
            cells = text.split("\t")
            if len(cells) >= 3:
                propiedades.append(SnrPropiedad(
                    matricula_inmobiliaria=cells[0].strip() if cells else "",
                    tipo=cells[1].strip() if len(cells) > 1 else "",
                    departamento=cells[2].strip() if len(cells) > 2 else "",
                    municipio=cells[3].strip() if len(cells) > 3 else "",
                    direccion=cells[4].strip() if len(cells) > 4 else "",
                    estado=cells[5].strip() if len(cells) > 5 else "",
                ))

        result.propiedades = propiedades
        result.total_propiedades = len(propiedades)
        result.tiene_propiedades = len(propiedades) > 0
        result.mensaje = f"SNR {documento}: {len(propiedades)} propiedad(es) encontrada(s)"

        return result
