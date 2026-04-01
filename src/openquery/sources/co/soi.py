"""SOI source — Colombian social security payment records.

Queries the SOI (Sistema Obligatorio de Información) / PILA platform
for social security payment history (salud, pensión, riesgos).

Flow:
1. Navigate to SOI consultation page
2. Select document type and enter number
3. Submit and parse payment records table

Source: https://www.soi.com.co/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.soi import SoiPago, SoiResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SOI_URL = "https://www.soi.com.co/"


@register
class SoiSource(BaseSource):
    """Query Colombian social security payment records (SOI/PILA)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.soi",
            display_name="SOI — Pago de Seguridad Social",
            description="Colombian social security payment records (SOI/PILA)",
            country="CO",
            url=SOI_URL,
            supported_inputs=[DocumentType.CEDULA, DocumentType.NIT],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type not in (DocumentType.CEDULA, DocumentType.NIT):
            raise SourceError("co.soi", f"Only cedula/NIT supported, got: {input.document_type}")
        tipo = "nit" if input.document_type == DocumentType.NIT else "cedula"
        return self._query(input.document_number, tipo, audit=input.audit)

    def _query(self, documento: str, tipo: str = "cedula", audit: bool = False) -> SoiResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.soi", tipo, documento)

        with browser.page(SOI_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_selector('input[type="text"], select', timeout=15000)
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
                    'input[type="text"][id*="identificacion"], '
                    'input[type="text"]'
                )
                if not doc_input:
                    raise SourceError("co.soi", "Could not find document input field")

                doc_input.fill(documento)
                logger.info("Searching SOI for: %s", documento)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="consultar"], button[id*="buscar"], '
                    'a[id*="consultar"]'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    doc_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, documento, tipo)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("co.soi", f"Query failed: {e}") from e

    def _parse_result(self, page, documento: str, tipo: str) -> SoiResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        result = SoiResult(
            queried_at=datetime.now(),
            documento=documento,
            tipo_documento=tipo,
        )

        # Try to extract name
        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if "nombre" in lower and ":" in stripped:
                result.nombre = stripped.split(":", 1)[1].strip()
                break

        # Extract payment records from table rows
        pagos: list[SoiPago] = []
        table_rows = page.query_selector_all("table tr, .registro-pago, .item-pago")

        for row in table_rows:
            cells = row.query_selector_all("td")
            if len(cells) >= 3:
                cell_texts = [c.inner_text().strip() for c in cells]
                pagos.append(SoiPago(
                    periodo=cell_texts[0] if cell_texts else "",
                    aportante=cell_texts[1] if len(cell_texts) > 1 else "",
                    tipo_aportante=cell_texts[2] if len(cell_texts) > 2 else "",
                    salud=cell_texts[3] if len(cell_texts) > 3 else "",
                    pension=cell_texts[4] if len(cell_texts) > 4 else "",
                    riesgos=cell_texts[5] if len(cell_texts) > 5 else "",
                    estado=cell_texts[6] if len(cell_texts) > 6 else "",
                ))

        result.pagos = pagos
        result.total_pagos = len(pagos)
        result.mensaje = f"SOI {documento}: {len(pagos)} pago(s) encontrado(s)"

        return result
