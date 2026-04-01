"""COPNIA source — Colombian professional engineering council.

Queries COPNIA for professional engineering license verification.

Flow:
1. Navigate to COPNIA professional consultation page
2. Enter document number
3. Submit and parse license information

Source: https://www.copnia.gov.co/tribunal-de-etica/consulta-de-profesionales
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.copnia import CopniaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

COPNIA_URL = "https://www.copnia.gov.co/tribunal-de-etica/consulta-de-profesionales"

DOC_TYPE_MAP = {
    DocumentType.CEDULA: "CC",
    DocumentType.NIT: "NI",
    DocumentType.PASSPORT: "PA",
}


@register
class CopniaSource(BaseSource):
    """Query Colombian professional engineering license (COPNIA)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.copnia",
            display_name="COPNIA \u2014 Consejo Prof. de Ingenier\u00eda",
            description="Colombian professional engineering council license verification (COPNIA)",
            country="CO",
            url=COPNIA_URL,
            supported_inputs=[DocumentType.CEDULA, DocumentType.NIT, DocumentType.PASSPORT],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type not in DOC_TYPE_MAP:
            raise SourceError(
                "co.copnia",
                f"Unsupported document type: {input.document_type}. Use cedula, NIT, or passport.",
            )
        return self._query(input.document_number, input.document_type, audit=input.audit)

    def _query(
        self, documento: str, doc_type: DocumentType, audit: bool = False,
    ) -> CopniaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.copnia", doc_type.value, documento)

        with browser.page(COPNIA_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                # Wait for form to load
                page.wait_for_selector(
                    'select, input[type="text"]',
                    timeout=15000,
                )
                page.wait_for_timeout(2000)

                # Select document type if dropdown exists
                doc_select = page.query_selector(
                    'select[id*="tipo"], select[name*="tipo"], select[id*="document"]'
                )
                if doc_select:
                    select_value = DOC_TYPE_MAP.get(doc_type, "CC")
                    page.select_option(
                        'select[id*="tipo"], select[name*="tipo"], select[id*="document"]',
                        value=select_value,
                        timeout=5000,
                    )
                    logger.info("Selected document type: %s", select_value)

                # Fill document number
                doc_input = page.query_selector(
                    'input[type="text"][id*="numero"], '
                    'input[type="text"][id*="documento"], '
                    'input[type="text"][id*="cedula"], '
                    'input[type="text"][name*="numero"], '
                    'input[type="text"]'
                )
                if not doc_input:
                    raise SourceError("co.copnia", "Could not find document input field")

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

                # Parse result
                result = self._parse_result(page, documento)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("co.copnia", f"Query failed: {e}") from e

    def _parse_result(self, page, documento: str) -> CopniaResult:
        """Parse the COPNIA result page for license information."""
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        # Check for no records
        no_records = any(phrase in body_lower for phrase in [
            "no se encontr",
            "sin registros",
            "no registra",
            "no aparece",
            "no tiene matr",
        ])

        has_records = any(phrase in body_lower for phrase in [
            "vigente",
            "matr\u00edcula",
            "matricula",
            "profesional registrado",
        ]) and not no_records

        # Extract fields from result
        nombre = ""
        matricula = ""
        estado_matricula = ""
        profesion = ""
        fecha_registro = ""

        for line in body_text.split("\n"):
            line_stripped = line.strip()
            line_lower = line_stripped.lower()

            if any(label in line_lower for label in ["nombre", "profesional"]):
                parts = line_stripped.split(":")
                if len(parts) > 1 and not nombre:
                    nombre = parts[1].strip()

            if any(label in line_lower for label in ["matr\u00edcula", "matricula", "n\u00famero"]):
                parts = line_stripped.split(":")
                if len(parts) > 1 and not matricula:
                    matricula = parts[1].strip()

            if "estado" in line_lower:
                parts = line_stripped.split(":")
                if len(parts) > 1 and not estado_matricula:
                    estado_matricula = parts[1].strip()

            if any(label in line_lower for label in ["profesi\u00f3n", "profesion", "t\u00edtulo", "titulo"]):
                parts = line_stripped.split(":")
                if len(parts) > 1 and not profesion:
                    profesion = parts[1].strip()

            if "fecha" in line_lower:
                parts = line_stripped.split(":")
                if len(parts) > 1 and not fecha_registro:
                    fecha_registro = parts[1].strip()

        mensaje = ""
        if no_records:
            mensaje = "No se encontr\u00f3 registro profesional en COPNIA"
        elif has_records:
            mensaje = "Profesional registrado en COPNIA"

        return CopniaResult(
            queried_at=datetime.now(),
            documento=documento,
            nombre=nombre,
            esta_registrado=has_records,
            matricula=matricula,
            estado_matricula=estado_matricula,
            profesion=profesion,
            fecha_registro=fecha_registro,
            mensaje=mensaje,
        )
