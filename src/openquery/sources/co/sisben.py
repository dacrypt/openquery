"""SISBEN source — Colombian socioeconomic classification lookup.

Queries the SISBEN (Sistema de Identificación de Potenciales Beneficiarios
de Programas Sociales) for group/subgroup classification.

Flow:
1. Navigate to the SISBEN consultation page
2. Select document type and enter number
3. Submit and parse result

Source: https://reportes.sisben.gov.co/dnp_sisbenconsulta
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.sisben import SisbenResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SISBEN_URL = "https://reportes.sisben.gov.co/dnp_sisbenconsulta"


@register
class SisbenSource(BaseSource):
    """Query Colombian SISBEN socioeconomic classification."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.sisben",
            display_name="SISBEN — Clasificación Socioeconómica",
            description="Colombian SISBEN socioeconomic classification (group/subgroup lookup)",
            country="CO",
            url=SISBEN_URL,
            supported_inputs=[DocumentType.CEDULA, DocumentType.PASSPORT],
            requires_captcha=True,  # Google reCAPTCHA v3
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type not in (DocumentType.CEDULA, DocumentType.PASSPORT):
            raise SourceError("co.sisben", f"Unsupported document type: {input.document_type}")
        return self._query(input.document_number, input.document_type, audit=input.audit)

    def _query(self, documento: str, doc_type: DocumentType, audit: bool = False) -> SisbenResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.sisben", doc_type.value, documento)

        with browser.page(SISBEN_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_selector('select, input[type="text"]', timeout=15000)
                page.wait_for_timeout(2000)

                # Select doc type
                doc_select = page.query_selector(
                    'select[id*="tipo"], select[name*="tipo"]'
                )
                if doc_select:
                    select_value = "CC" if doc_type == DocumentType.CEDULA else "PA"
                    page.select_option(
                        'select[id*="tipo"], select[name*="tipo"]',
                        value=select_value,
                        timeout=5000,
                    )

                # Fill document number
                doc_input = page.query_selector(
                    'input[type="text"][id*="numero"], '
                    'input[type="text"][id*="documento"], '
                    'input[type="text"]'
                )
                if not doc_input:
                    raise SourceError("co.sisben", "Could not find document input field")

                doc_input.fill(documento)

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

                result = self._parse_result(page, documento, doc_type)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("co.sisben", f"Query failed: {e}") from e

    def _parse_result(self, page, documento: str, doc_type: DocumentType) -> SisbenResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        result = SisbenResult(
            queried_at=datetime.now(),
            documento=documento,
            tipo_documento=doc_type.value,
        )

        field_map = {
            "nombre": "nombre",
            "grupo": "grupo",
            "subgrupo": "subgrupo",
            "departamento": "departamento",
            "municipio": "municipio",
            "ficha": "ficha",
            "puntaje": "puntaje",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_map.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    setattr(result, field, value)
                    break

        if not result.grupo and "no se encontr" in body_text.lower():
            result.mensaje = "No se encontró registro en SISBEN"
        elif result.grupo:
            result.mensaje = f"Grupo SISBEN: {result.grupo}"

        return result
