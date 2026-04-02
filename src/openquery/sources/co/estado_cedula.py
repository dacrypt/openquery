"""Estado de Cédula source — Colombian ID card status.

Queries the Registraduría Nacional for cédula status (vigente, cancelada, etc.).

Flow:
1. Navigate to the Registraduría consultation page
2. Enter cédula number and date of issuance
3. Submit and parse result

Source: https://consultasrc.registraduria.gov.co/ProyectoSCCRC/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.estado_cedula import EstadoCedulaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

REGISTRADURIA_URL = "https://consultasrc.registraduria.gov.co/ProyectoSCCRC/"


@register
class EstadoCedulaSource(BaseSource):
    """Query Colombian cédula status (Registraduría Nacional)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.estado_cedula",
            display_name="Registraduría — Estado de Cédula",
            description="Colombian cédula (ID card) status check from Registraduría Nacional",
            country="CO",
            url=REGISTRADURIA_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CEDULA:
            raise SourceError("co.estado_cedula", f"Only cedula supported, got: {input.document_type}")

        fecha = input.extra.get("fecha_expedicion", "").strip()
        return self._query(input.document_number, fecha, audit=input.audit)

    def _query(self, cedula: str, fecha_expedicion: str = "", audit: bool = False) -> EstadoCedulaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.estado_cedula", "cedula", cedula)

        with browser.page(REGISTRADURIA_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(3000)

                # Fill cedula
                cedula_input = page.query_selector(
                    'input[type="text"][id*="cedula"], '
                    'input[type="text"][id*="numero"], '
                    'input[type="text"][name*="cedula"], '
                    'input[type="text"][name*="numero"], '
                    'input[type="text"]'
                )
                if not cedula_input:
                    raise SourceError("co.estado_cedula", "Could not find cedula input field")

                cedula_input.fill(cedula)

                # Fill date if provided
                if fecha_expedicion:
                    date_input = page.query_selector(
                        'input[type="text"][id*="fecha"], '
                        'input[type="date"][id*="fecha"], '
                        'input[type="text"][name*="fecha"]'
                    )
                    if date_input:
                        date_input.fill(fecha_expedicion)

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

                result = self._parse_result(page, cedula, fecha_expedicion)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("co.estado_cedula", f"Query failed: {e}") from e

    def _parse_result(self, page, cedula: str, fecha: str) -> EstadoCedulaResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        estado = "Desconocido"
        nombre = ""
        lugar = ""

        if "vigente" in body_lower:
            estado = "Vigente"
        elif "cancelada" in body_lower and "muerte" in body_lower:
            estado = "Cancelada por muerte"
        elif "cancelada" in body_lower:
            estado = "Cancelada"
        elif "no registra" in body_lower or "no se encontr" in body_lower:
            estado = "No registrada"

        # Try to extract name and place
        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if "nombre" in lower and ":" in stripped:
                nombre = stripped.split(":", 1)[1].strip()
            elif "lugar" in lower and ":" in stripped:
                lugar = stripped.split(":", 1)[1].strip()

        return EstadoCedulaResult(
            queried_at=datetime.now(),
            cedula=cedula,
            fecha_expedicion=fecha,
            estado=estado,
            nombre=nombre,
            lugar_expedicion=lugar,
            mensaje=f"Cédula {cedula}: {estado}",
        )
