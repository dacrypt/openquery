"""CUFE DIAN source — Colombian electronic invoice verification.

Queries the DIAN electronic invoice catalog to verify a CUFE
(Codigo Unico de Factura Electronica).

Flow:
1. Navigate to the DIAN VPFE catalog
2. Enter the CUFE code
3. Submit and parse invoice details

Source: https://catalogo-vpfe.dian.gov.co/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.cufe_dian import CufeDianResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CUFE_URL = "https://catalogo-vpfe.dian.gov.co/"


@register
class CufeDianSource(BaseSource):
    """Query DIAN electronic invoice verification by CUFE."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.cufe_dian",
            display_name="DIAN \u2014 Verificaci\u00f3n de Factura Electr\u00f3nica",
            description="Colombian electronic invoice verification by CUFE (DIAN)",
            country="CO",
            url=CUFE_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CUSTOM:
            raise SourceError(
                "co.cufe_dian",
                f"Unsupported document type: {input.document_type}. Use CUSTOM with the CUFE as document_number.",
            )
        cufe = input.document_number.strip()
        if not cufe:
            raise SourceError("co.cufe_dian", "CUFE code is required in document_number")
        return self._query(cufe, audit=input.audit)

    def _query(self, cufe: str, audit: bool = False) -> CufeDianResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.cufe_dian", "cufe", cufe)

        with browser.page(CUFE_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_selector('input[type="text"]', timeout=15000)
                page.wait_for_timeout(2000)

                # Fill CUFE code
                cufe_input = page.query_selector(
                    'input[type="text"][id*="cufe"], '
                    'input[type="text"][id*="CUFE"], '
                    'input[type="text"][id*="codigo"], '
                    'input[type="text"][id*="document"], '
                    'input[type="text"]'
                )
                if not cufe_input:
                    raise SourceError("co.cufe_dian", "Could not find CUFE input field")

                cufe_input.fill(cufe)
                logger.info("Filled CUFE: %s...", cufe[:16])

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="consultar"], button[id*="buscar"], '
                    'button[id*="verificar"], '
                    'input[id*="consultar"], input[id*="buscar"]'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    cufe_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, cufe)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("co.cufe_dian", f"Query failed: {e}") from e

    def _parse_result(self, page, cufe: str) -> CufeDianResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        result = CufeDianResult(
            queried_at=datetime.now(),
            cufe=cufe,
        )

        field_map = {
            "nit emisor": "emisor_nit",
            "emisor": "emisor_nombre",
            "nit receptor": "receptor_nit",
            "receptor": "receptor_nombre",
            "n\u00famero de factura": "numero_factura",
            "numero de factura": "numero_factura",
            "n\u00famero factura": "numero_factura",
            "numero factura": "numero_factura",
            "fecha de emisi\u00f3n": "fecha_emision",
            "fecha de emision": "fecha_emision",
            "fecha emisi\u00f3n": "fecha_emision",
            "fecha emision": "fecha_emision",
            "valor total": "valor_total",
            "total": "valor_total",
            "estado": "estado",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_map.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    # For emisor/receptor, avoid overwriting NIT fields
                    if field == "emisor_nombre" and result.emisor_nit and value == result.emisor_nit:
                        continue
                    if field == "receptor_nombre" and result.receptor_nit and value == result.receptor_nit:
                        continue
                    setattr(result, field, value)
                    break

        # Determine validity
        body_lower = body_text.lower()
        if result.estado:
            result.es_valida = "aprobad" in result.estado.lower() or "valid" in result.estado.lower()
        if result.numero_factura:
            result.mensaje = f"Factura {result.numero_factura} - {result.estado}"
        elif "no se encontr" in body_lower or "no existe" in body_lower:
            result.mensaje = "No se encontr\u00f3 factura con el CUFE proporcionado"
        elif "error" in body_lower:
            result.mensaje = "Error al consultar el CUFE"

        return result
