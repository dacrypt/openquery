"""ADRES source — Colombian health insurance affiliation (BDUA).

Queries ADRES (formerly FOSYGA) for health system affiliation status.
The actual form is inside an iframe pointing to an ASP.NET application.

Flow:
1. Navigate to iframe URL directly
2. Select document type
3. Enter document number
4. Click "Consultar"
5. Parse result table
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.adres import AdresResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

# Go directly to the iframe URL — bypasses the parent page
ADRES_URL = "https://aplicaciones.adres.gov.co/BDUA_Internet/Pages/ConsultarAfiliadoWeb_2.aspx"

DOC_TYPE_MAP = {
    DocumentType.CEDULA: "CC",
    DocumentType.NIT: "NI",
    DocumentType.PASSPORT: "PA",
}


@register
class AdresSource(BaseSource):
    """Query Colombian health insurance affiliation (ADRES/FOSYGA)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.adres",
            display_name="ADRES — Afiliacion Salud (EPS)",
            description="Colombian health system affiliation, EPS, and regime status",
            country="CO",
            url=ADRES_URL,
            supported_inputs=[DocumentType.CEDULA, DocumentType.NIT, DocumentType.PASSPORT],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type not in DOC_TYPE_MAP:
            raise SourceError("co.adres", f"Unsupported document type: {input.document_type}")
        return self._query(input.document_type, input.document_number, audit=input.audit)

    def _query(
        self,
        doc_type: DocumentType,
        doc_number: str,
        audit: bool = False,
    ) -> AdresResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("co.adres", str(doc_type), doc_number)

        with browser.page(ADRES_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                # Wait for the ASP.NET form — exact IDs from site inspection
                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Select document type — exact ID: #tipoDoc
                adres_type = DOC_TYPE_MAP[doc_type]
                doc_select = page.query_selector(
                    "#tipoDoc, #ddlTipoDocumento, select[name='tipoDoc']"
                )
                if doc_select:
                    page.select_option(
                        "#tipoDoc, #ddlTipoDocumento",
                        value=adres_type,
                    )
                logger.info("Selected document type: %s", adres_type)

                # Fill document number — exact ID: #txtNumDoc
                num_input = page.query_selector(
                    "#txtNumDoc, #txtNumDocumento, input[name='txtNumDoc']"
                )
                if not num_input:
                    raise SourceError("co.adres", "Could not find document number input")
                num_input.fill(doc_number)
                logger.info("Filled document number")

                # Solve reCAPTCHA Enterprise v3 if present
                from openquery.core.captcha_middleware import solve_page_captchas

                solve_page_captchas(page)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Click "Consultar" — exact ID: #btnConsultar
                submit = page.query_selector("#btnConsultar, input[name='btnConsultar']")
                if submit:
                    submit.click()
                else:
                    num_input.press("Enter")

                # Wait for results
                page.wait_for_timeout(3000)
                page.wait_for_selector(
                    "table, .grid, #gvAfiliados, #lblMensaje, .resultado",
                    timeout=15000,
                )

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, doc_type, doc_number)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("co.adres", f"Query failed: {e}") from e

    def _parse_result(
        self,
        page,
        doc_type: DocumentType,
        doc_number: str,
    ) -> AdresResult:
        """Parse the ADRES result page."""
        from datetime import datetime

        body_text = page.inner_text("body")
        result = AdresResult(
            queried_at=datetime.now(),
            cedula=doc_number,
            tipo_documento=str(doc_type),
        )

        # Try to parse from a result table (GridView)
        rows = page.query_selector_all("table tr, #gvAfiliados tr, .grid tr")

        if len(rows) >= 2:
            # First row is header, second row is data
            cells = rows[1].query_selector_all("td")
            if cells:
                values = [(c.inner_text() or "").strip() for c in cells]
                # Typical columns: TipoDoc, Numero, Nombre, Estado, EPS, Regimen,
                #                   TipoAfiliado, Municipio, Depto, FechaAfil
                if len(values) >= 5:
                    result.nombre = values[2] if len(values) > 2 else ""
                    result.estado_afiliacion = values[3] if len(values) > 3 else ""
                    result.eps = values[4] if len(values) > 4 else ""
                    result.regimen = values[5] if len(values) > 5 else ""
                    result.tipo_afiliado = values[6] if len(values) > 6 else ""
                    result.municipio = values[7] if len(values) > 7 else ""
                    result.departamento = values[8] if len(values) > 8 else ""
                    result.fecha_afiliacion = values[9] if len(values) > 9 else ""

        # Fallback: parse key-value pairs from text
        if not result.eps:
            for pattern, field in [
                (r"EPS[:\s]+([^\n]+)", "eps"),
                (r"Estado[:\s]+([^\n]+)", "estado_afiliacion"),
                (r"R[eé]gimen[:\s]+([^\n]+)", "regimen"),
            ]:
                m = re.search(pattern, body_text, re.IGNORECASE)
                if m:
                    setattr(result, field, m.group(1).strip())

        return result
