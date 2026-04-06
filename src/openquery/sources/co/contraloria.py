"""Contraloría General de la República source — Colombian fiscal records.

Queries the Contraloría General for fiscal responsibility records
(antecedentes fiscales / responsabilidad fiscal).

Flow:
1. Navigate to the CGR consultation page
2. Select document type and enter document number
3. Submit and parse result

Source: https://www.contraloria.gov.co/web/guest/persona-natural
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.contraloria import ContraloriaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CONTRALORIA_URL = "https://cfiscal.contraloria.gov.co/Certificados/CertificadoPersonaNatural.aspx"


@register
class ContraloriaSource(BaseSource):
    """Query Colombian fiscal responsibility records (Contraloría General)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.contraloria",
            display_name="Contraloría — Antecedentes Fiscales",
            description="Colombian fiscal responsibility and background records (CGR)",
            country="CO",
            url=CONTRALORIA_URL,
            supported_inputs=[DocumentType.CEDULA, DocumentType.NIT, DocumentType.PASSPORT],
            requires_captcha=True,  # reCAPTCHA v2 on the form
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type not in (
            DocumentType.CEDULA,
            DocumentType.NIT,
            DocumentType.PASSPORT,
        ):
            raise SourceError(
                "co.contraloria",
                f"Unsupported document type: {input.document_type}. Use cedula, NIT, or passport.",
            )
        return self._query(input.document_number, input.document_type, audit=input.audit)

    def _query(
        self, documento: str, doc_type: DocumentType, audit: bool = False
    ) -> ContraloriaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("co.contraloria", doc_type.value, documento)

        doc_type_map = {
            DocumentType.CEDULA: "CC",
            DocumentType.NIT: "NI",
            DocumentType.PASSPORT: "PA",
        }

        with browser.page(CONTRALORIA_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                # Wait for ASP.NET form to load — exact selectors from site inspection
                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(2000)

                # Select document type — exact ID: #ddlTipoDocumento
                doc_select = page.query_selector(
                    '#ddlTipoDocumento, select[id*="TipoDocumento"], select[id*="tipo"]'
                )
                if doc_select:
                    select_value = doc_type_map.get(doc_type, "CC")
                    page.select_option(
                        '#ddlTipoDocumento, select[id*="TipoDocumento"], select[id*="tipo"]',
                        value=select_value,
                        timeout=5000,
                    )
                    logger.info("Selected document type: %s", select_value)

                # Fill document number — exact ID: #txtNumeroDocumento
                doc_input = page.query_selector(
                    '#txtNumeroDocumento, input[id*="NumeroDocumento"], input[type="text"]'
                )
                if not doc_input:
                    raise SourceError("co.contraloria", "Could not find document input field")

                doc_input.fill(documento)
                logger.info("Filled document: %s", documento)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit — exact ID: #btnBuscar
                submit_btn = page.query_selector(
                    "#btnBuscar, "
                    'input[id*="btnBuscar"], '
                    'button[type="submit"], input[type="submit"]'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    doc_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                # Parse result
                result = self._parse_result(page, documento, doc_type)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("co.contraloria", f"Query failed: {e}") from e

    def _parse_result(self, page, documento: str, doc_type: DocumentType) -> ContraloriaResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        no_records = any(
            phrase in body_lower
            for phrase in [
                "no se encontr",
                "no registra",
                "no aparece",
                "sin antecedentes",
                "no figura",
                "no tiene responsabilidad",
            ]
        )

        has_records = (
            any(
                phrase in body_lower
                for phrase in [
                    "responsabilidad fiscal",
                    "bolet",
                    "registra antecedentes",
                    "fiscal vigente",
                ]
            )
            and not no_records
        )

        # Try to extract name
        nombre = ""
        for line in body_text.split("\n"):
            line_stripped = line.strip()
            if any(label in line_stripped.lower() for label in ["nombre", "razón social"]):
                parts = line_stripped.split(":")
                if len(parts) > 1:
                    nombre = parts[1].strip()
                    break

        mensaje = ""
        if no_records:
            mensaje = "No registra antecedentes fiscales"
        elif has_records:
            mensaje = "Registra antecedentes de responsabilidad fiscal"

        return ContraloriaResult(
            queried_at=datetime.now(),
            documento=documento,
            tipo_documento=doc_type.value,
            nombre=nombre,
            tiene_antecedentes_fiscales=has_records,
            mensaje=mensaje,
        )
