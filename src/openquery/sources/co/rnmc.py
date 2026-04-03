"""RNMC source — Colombian National Registry of Corrective Measures.

Queries the RNMC (Registro Nacional de Medidas Correctivas) from the
Policía Nacional for police corrective measures (comparendos de policía).

Flow:
1. Navigate to RNMC consultation page
2. Enter cédula and optionally date
3. Submit and parse result

Source: https://srvcnpc.policia.gov.co/PSC/frm_cnp_consulta.aspx
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.rnmc import MedidaCorrectiva, RnmcResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

RNMC_URL = "https://srvcnpc.policia.gov.co/PSC/frm_cnp_consulta.aspx"


@register
class RnmcSource(BaseSource):
    """Query Colombian corrective measures registry (RNMC)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.rnmc",
            display_name="RNMC — Medidas Correctivas",
            description="Colombian National Registry of Corrective Measures (police comparendos)",
            country="CO",
            url=RNMC_URL,
            supported_inputs=[DocumentType.CEDULA, DocumentType.PASSPORT],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type not in (DocumentType.CEDULA, DocumentType.PASSPORT):
            raise SourceError("co.rnmc", f"Unsupported document type: {input.document_type}")

        fecha = input.extra.get("fecha_nacimiento", "").strip()
        return self._query(input.document_number, input.document_type, fecha, audit=input.audit)

    def _query(self, documento: str, doc_type: DocumentType, fecha: str = "", audit: bool = False) -> RnmcResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.rnmc", doc_type.value, documento)

        with browser.page(RNMC_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(3000)

                # Select document type — exact ASP.NET IDs from site inspection
                doc_select = page.query_selector(
                    '#ctl00_ContentPlaceHolder3_ddlTipoDoc, '
                    'select[id*="TipoDoc"], select[id*="tipo"]'
                )
                if doc_select:
                    select_value = "55" if doc_type == DocumentType.CEDULA else "58"
                    page.select_option(
                        '#ctl00_ContentPlaceHolder3_ddlTipoDoc, '
                        'select[id*="TipoDoc"], select[id*="tipo"]',
                        value=select_value,
                        timeout=5000,
                    )

                # Fill document number — exact ID from site inspection
                doc_input = page.query_selector(
                    '#ctl00_ContentPlaceHolder3_txtExpediente, '
                    'input[id*="txtExpediente"], '
                    'input[type="text"]'
                )
                if not doc_input:
                    raise SourceError("co.rnmc", "Could not find document input field")

                doc_input.fill(documento)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit via direct __doPostBack JavaScript call
                # ASP.NET WebForms uses __doPostBack for <a> links — calling it
                # directly avoids ElementHandle detach issues
                try:
                    page.evaluate(
                        "__doPostBack('ctl00$ContentPlaceHolder3$btnConsultar','')"
                    )
                except Exception:
                    # Fallback: try clicking the element
                    submit_btn = page.query_selector(
                        '#ctl00_ContentPlaceHolder3_btnConsultar, '
                        'a[id*="btnConsultar"]'
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
                raise SourceError("co.rnmc", f"Query failed: {e}") from e

    def _parse_result(self, page, documento: str) -> RnmcResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        no_records = any(phrase in body_lower for phrase in [
            "no registra",
            "no tiene medidas",
            "no se encontr",
            "sin medidas",
        ])

        has_records = any(phrase in body_lower for phrase in [
            "medida correctiva",
            "infracción",
            "comparendo",
        ]) and not no_records

        # Try to extract name
        nombre = ""
        for line in body_text.split("\n"):
            stripped = line.strip()
            if "nombre" in stripped.lower() and ":" in stripped:
                nombre = stripped.split(":", 1)[1].strip()
                break

        # Try to parse measures from table rows
        medidas = []
        table_rows = page.query_selector_all("table tr")
        for row in table_rows:
            cells = row.query_selector_all("td")
            if len(cells) >= 3:
                cell_texts = [c.inner_text().strip() for c in cells]
                medidas.append(MedidaCorrectiva(
                    tipo_medida=cell_texts[0] if cell_texts else "",
                    descripcion=cell_texts[1] if len(cell_texts) > 1 else "",
                    fecha_imposicion=cell_texts[2] if len(cell_texts) > 2 else "",
                    estado=cell_texts[3] if len(cell_texts) > 3 else "",
                    localidad=cell_texts[4] if len(cell_texts) > 4 else "",
                ))

        mensaje = ""
        if no_records:
            mensaje = "No registra medidas correctivas"
        elif has_records:
            mensaje = f"Registra {len(medidas)} medida(s) correctiva(s)"

        return RnmcResult(
            queried_at=datetime.now(),
            cedula=documento,
            nombre=nombre,
            tiene_medidas=has_records,
            total_medidas=len(medidas),
            medidas=medidas,
            mensaje=mensaje,
        )
