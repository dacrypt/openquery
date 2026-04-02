"""Estado Trámite de Cédula source — Colombian ID card processing status.

Queries the Registraduría for cédula processing/issuance status.

Flow:
1. Navigate to Registraduría tramite consultation page
2. Enter cédula number
3. Submit and parse processing status

Source: https://wsp.registraduria.gov.co/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.estado_tramite_cedula import EstadoTramiteCedulaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

REGISTRADURIA_TRAMITE_URL = "https://wsp.registraduria.gov.co/"


@register
class EstadoTramiteCedulaSource(BaseSource):
    """Query Colombian cédula processing/issuance status (Registraduría)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.estado_tramite_cedula",
            display_name="Registraduría — Estado de Trámite de Cédula",
            description="Colombian ID card processing/issuance status from Registraduría",
            country="CO",
            url=REGISTRADURIA_TRAMITE_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CEDULA:
            raise SourceError(
                "co.estado_tramite_cedula",
                f"Only cedula supported, got: {input.document_type}",
            )

        return self._query(input.document_number, audit=input.audit)

    def _query(self, cedula: str, audit: bool = False) -> EstadoTramiteCedulaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.estado_tramite_cedula", "cedula", cedula)

        with browser.page(REGISTRADURIA_TRAMITE_URL) as page:
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
                    raise SourceError(
                        "co.estado_tramite_cedula",
                        "Could not find cedula input field",
                    )

                cedula_input.fill(cedula)
                logger.info("Filled cedula: %s", cedula)

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
                raise SourceError(
                    "co.estado_tramite_cedula", f"Query failed: {e}"
                ) from e

    def _parse_result(self, page, cedula: str) -> EstadoTramiteCedulaResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        estado_tramite = "Desconocido"
        fecha_solicitud = ""
        registraduria = ""

        # Determine processing status
        if "listo para entrega" in body_lower or "puede reclamar" in body_lower:
            estado_tramite = "Listo para entrega"
        elif "en proceso" in body_lower or "en producción" in body_lower:
            estado_tramite = "En proceso"
        elif "entregado" in body_lower:
            estado_tramite = "Entregado"
        elif "no registra" in body_lower or "no se encontr" in body_lower:
            estado_tramite = "No registra trámite"

        # Extract date and registraduría from key-value lines
        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if "fecha" in lower and "solicitud" in lower and ":" in stripped:
                fecha_solicitud = stripped.split(":", 1)[1].strip()
            elif "registradur" in lower and ":" in stripped:
                registraduria = stripped.split(":", 1)[1].strip()

        return EstadoTramiteCedulaResult(
            queried_at=datetime.now(),
            cedula=cedula,
            estado_tramite=estado_tramite,
            fecha_solicitud=fecha_solicitud,
            registraduria=registraduria,
            mensaje=f"Cédula {cedula}: {estado_tramite}",
        )
