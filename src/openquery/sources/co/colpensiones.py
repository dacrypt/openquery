"""Colpensiones source — Colombian pension affiliation.

Queries Colpensiones for pension affiliation status.

Flow:
1. Navigate to Colpensiones consultation page
2. Enter cédula number
3. Submit and parse result

Source: https://www.colpensiones.gov.co/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.colpensiones import ColpensionesResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

COLPENSIONES_URL = "https://www.colpensiones.gov.co/afiliados-y-pensionados/afiliados/consulta-de-afiliacion/"


@register
class ColpensionesSource(BaseSource):
    """Query Colombian pension affiliation (Colpensiones)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.colpensiones",
            display_name="Colpensiones — Afiliación a Pensiones",
            description="Colombian pension affiliation certificate from Colpensiones",
            country="CO",
            url=COLPENSIONES_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=True,
            requires_browser=True,
            rate_limit_rpm=5,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CEDULA:
            raise SourceError("co.colpensiones", f"Only cedula supported, got: {input.document_type}")
        return self._query(input.document_number, audit=input.audit)

    def _query(self, cedula: str, audit: bool = False) -> ColpensionesResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.colpensiones", "cedula", cedula)

        with browser.page(COLPENSIONES_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill cedula
                cedula_input = page.query_selector(
                    'input[type="text"][id*="cedula"], '
                    'input[type="text"][id*="numero"], '
                    'input[type="text"][id*="documento"], '
                    'input[type="text"]'
                )
                if not cedula_input:
                    raise SourceError("co.colpensiones", "Could not find cedula input field")

                cedula_input.fill(cedula)

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
                    cedula_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, cedula)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("co.colpensiones", f"Query failed: {e}") from e

    def _parse_result(self, page, cedula: str) -> ColpensionesResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        esta_afiliado = any(phrase in body_lower for phrase in [
            "afiliado activo",
            "está afiliado",
            "se encuentra afiliado",
        ])

        no_afiliado = any(phrase in body_lower for phrase in [
            "no se encuentra",
            "no está afiliado",
            "no registra",
        ])

        estado = "Desconocido"
        if esta_afiliado:
            estado = "Afiliado activo"
        elif no_afiliado:
            estado = "No afiliado"

        nombre = ""
        for line in body_text.split("\n"):
            stripped = line.strip()
            if "nombre" in stripped.lower() and ":" in stripped:
                nombre = stripped.split(":", 1)[1].strip()
                break

        return ColpensionesResult(
            queried_at=datetime.now(),
            cedula=cedula,
            nombre=nombre,
            esta_afiliado=esta_afiliado,
            estado=estado,
            mensaje=f"Colpensiones: {estado}",
        )
