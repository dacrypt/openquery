"""Defunción source — Colombian cédula vigency (alive/deceased) check.

Queries the Registraduría Nacional for cédula vigency status.

Flow:
1. Navigate to Registraduría consultation page
2. Enter cédula number
3. Parse result for vigente/cancelada por muerte/no registra

Source: https://consultasrc.registraduria.gov.co/ProyectoSCCRC/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.defuncion import DefuncionResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

REGISTRADURIA_URL = "https://consultasrc.registraduria.gov.co/ProyectoSCCRC/"


@register
class DefuncionSource(BaseSource):
    """Query Colombian cédula vigency / alive-deceased status (Registraduría)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.defuncion",
            display_name="Registraduría — Vigencia de Cédula",
            description="Colombian cédula vigency check (alive/deceased status)",
            country="CO",
            url=REGISTRADURIA_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CEDULA:
            raise SourceError("co.defuncion", f"Only cedula supported, got: {input.document_type}")
        return self._query(input.document_number, audit=input.audit)

    def _query(self, cedula: str, audit: bool = False) -> DefuncionResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.defuncion", "cedula", cedula)

        with browser.page(REGISTRADURIA_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill cedula
                cedula_input = page.query_selector(
                    'input[type="text"][id*="cedula"], '
                    'input[type="text"][id*="numero"], '
                    'input[type="text"][name*="cedula"], '
                    'input[type="text"][name*="numero"], '
                    'input[type="text"]'
                )
                if not cedula_input:
                    raise SourceError("co.defuncion", "Could not find cedula input field")

                cedula_input.fill(cedula)

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
                raise SourceError("co.defuncion", f"Query failed: {e}") from e

    def _parse_result(self, page, cedula: str) -> DefuncionResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        estado = "Desconocido"
        esta_vivo = True

        if "vigente" in body_lower:
            estado = "Vigente"
            esta_vivo = True
        elif "cancelada" in body_lower and "muerte" in body_lower:
            estado = "Cancelada por muerte"
            esta_vivo = False
        elif "cancelada" in body_lower:
            estado = "Cancelada"
            esta_vivo = False
        elif "no registra" in body_lower or "no se encontr" in body_lower:
            estado = "No registrada"

        nombre = ""
        for line in body_text.split("\n"):
            stripped = line.strip()
            if "nombre" in stripped.lower() and ":" in stripped:
                nombre = stripped.split(":", 1)[1].strip()
                break

        return DefuncionResult(
            queried_at=datetime.now(),
            cedula=cedula,
            estado=estado,
            nombre=nombre,
            esta_vivo=esta_vivo,
            mensaje=f"Cédula {cedula}: {estado}",
        )
