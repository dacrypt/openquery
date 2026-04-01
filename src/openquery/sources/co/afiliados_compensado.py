"""Afiliados Compensado source — Colombian compensation fund affiliation.

Queries the Superintendencia del Subsidio Familiar for compensation fund
(Caja de Compensación) affiliation status by document number.

Flow:
1. Navigate to SSF consultation page
2. Select document type and enter number
3. Submit and parse affiliation details

Source: https://www.ssf.gov.co/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.afiliados_compensado import AfiliadosCompensadoResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SSF_URL = "https://www.ssf.gov.co/"


@register
class AfiliadosCompensadoSource(BaseSource):
    """Query Colombian compensation fund affiliation (SSF)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.afiliados_compensado",
            display_name="Cajas de Compensaci\u00f3n \u2014 Afiliados",
            description="Colombian compensation fund (Caja de Compensaci\u00f3n) affiliation status",
            country="CO",
            url=SSF_URL,
            supported_inputs=[DocumentType.CEDULA, DocumentType.PASSPORT],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type not in (DocumentType.CEDULA, DocumentType.PASSPORT):
            raise SourceError(
                "co.afiliados_compensado",
                f"Unsupported document type: {input.document_type}. Use cedula or passport.",
            )
        tipo = "CC" if input.document_type == DocumentType.CEDULA else "PA"
        return self._query(input.document_number, tipo, audit=input.audit)

    def _query(self, documento: str, tipo: str, audit: bool = False) -> AfiliadosCompensadoResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.afiliados_compensado", tipo, documento)

        with browser.page(SSF_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                # Wait for form to load
                page.wait_for_selector(
                    'input[type="text"], select',
                    timeout=15000,
                )
                page.wait_for_timeout(2000)

                # Try to select document type
                doc_type_select = page.query_selector(
                    'select[id*="tipo"], select[id*="document"], '
                    'select[name*="tipo"], select[name*="document"]'
                )
                if doc_type_select:
                    doc_type_select.select_option(label=tipo)
                    logger.info("Selected document type: %s", tipo)

                # Fill document number
                doc_input = page.query_selector(
                    'input[type="text"][id*="numero"], '
                    'input[type="text"][id*="cedula"], '
                    'input[type="text"][id*="documento"], '
                    'input[type="text"][name*="numero"], '
                    'input[type="text"]'
                )
                if not doc_input:
                    raise SourceError("co.afiliados_compensado", "Could not find document input field")

                doc_input.fill(documento)
                logger.info("Filled document: %s", documento)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="consultar"], button[id*="buscar"], '
                    'a[id*="consultar"], a[id*="buscar"]'
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
                raise SourceError("co.afiliados_compensado", f"Query failed: {e}") from e

    def _parse_result(self, page, documento: str, tipo: str) -> AfiliadosCompensadoResult:
        """Parse the SSF result page for affiliation info."""
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        # Check for no records
        no_records = any(phrase in body_lower for phrase in [
            "no se encontr",
            "no aparece",
            "no registra",
            "sin resultados",
            "no tiene afiliaci",
        ])

        nombre = ""
        caja_compensacion = ""
        estado = ""
        categoria = ""
        empresa = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()

            if any(label in lower for label in ["nombre", "afiliado"]):
                parts = stripped.split(":")
                if len(parts) > 1 and not nombre:
                    nombre = parts[1].strip()

            if any(label in lower for label in ["caja de compensaci", "caja compensaci", "entidad"]):
                parts = stripped.split(":")
                if len(parts) > 1 and not caja_compensacion:
                    caja_compensacion = parts[1].strip()

            if "estado" in lower and ":" in stripped:
                parts = stripped.split(":")
                if len(parts) > 1 and not estado:
                    estado = parts[1].strip()

            if any(label in lower for label in ["categor", "tipo afiliado"]):
                parts = stripped.split(":")
                if len(parts) > 1 and not categoria:
                    categoria = parts[1].strip()

            if any(label in lower for label in ["empresa", "empleador", "patrono"]):
                parts = stripped.split(":")
                if len(parts) > 1 and not empresa:
                    empresa = parts[1].strip()

        # Also try extracting from table rows
        if not caja_compensacion:
            rows = page.query_selector_all("table tr, .resultado td, .info-row")
            for row in rows:
                text = row.inner_text().strip()
                text_lower = text.lower()
                if "caja" in text_lower and ":" in text:
                    caja_compensacion = text.split(":", 1)[1].strip()
                elif "estado" in text_lower and ":" in text:
                    estado = text.split(":", 1)[1].strip()
                elif "categor" in text_lower and ":" in text:
                    categoria = text.split(":", 1)[1].strip()
                elif "empresa" in text_lower and ":" in text:
                    empresa = text.split(":", 1)[1].strip()

        esta_afiliado = bool(caja_compensacion) and not no_records

        mensaje = ""
        if no_records:
            mensaje = "No se encontr\u00f3 afiliaci\u00f3n a caja de compensaci\u00f3n"
        elif esta_afiliado:
            mensaje = f"Afiliado a {caja_compensacion}"

        return AfiliadosCompensadoResult(
            queried_at=datetime.now(),
            documento=documento,
            tipo_documento=tipo,
            nombre=nombre,
            esta_afiliado=esta_afiliado,
            caja_compensacion=caja_compensacion,
            estado=estado,
            categoria=categoria,
            empresa=empresa,
            mensaje=mensaje,
        )
