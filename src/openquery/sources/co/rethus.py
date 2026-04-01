"""RETHUS source — Colombian health workforce professional registry.

Queries the RETHUS (Registro Nacional del Talento Humano en Salud)
for health professional registration status.

Flow:
1. Navigate to RETHUS consultation page
2. Enter document number
3. Parse result for profession, registration, university

Source: https://rfrfrethus2.minsalud.gov.co/ReTHUS/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.rethus import RethusResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

RETHUS_URL = "https://rfrfrethus2.minsalud.gov.co/ReTHUS/"


@register
class RethusSource(BaseSource):
    """Query Colombian health workforce registry (RETHUS)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.rethus",
            display_name="RETHUS — Talento Humano en Salud",
            description="Colombian health workforce professional registry (RETHUS)",
            country="CO",
            url=RETHUS_URL,
            supported_inputs=[DocumentType.CEDULA, DocumentType.PASSPORT],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type not in (DocumentType.CEDULA, DocumentType.PASSPORT):
            raise SourceError("co.rethus", f"Only cedula/passport supported, got: {input.document_type}")
        return self._query(input.document_number, input.document_type, audit=input.audit)

    def _query(self, documento: str, tipo: str = "cedula", audit: bool = False) -> RethusResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.rethus", tipo, documento)

        with browser.page(RETHUS_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_selector('input[type="text"]', timeout=15000)
                page.wait_for_timeout(2000)

                # Select document type if dropdown exists
                tipo_select = page.query_selector(
                    'select[id*="tipo"], select[id*="document"], select[name*="tipo"]'
                )
                if tipo_select:
                    if tipo == "pasaporte":
                        tipo_select.select_option(label="Pasaporte")
                    else:
                        tipo_select.select_option(label="Cédula de Ciudadanía")

                # Fill document number
                doc_input = page.query_selector(
                    'input[type="text"][id*="documento"], '
                    'input[type="text"][id*="numero"], '
                    'input[type="text"][id*="cedula"], '
                    'input[type="text"]'
                )
                if not doc_input:
                    raise SourceError("co.rethus", "Could not find document input field")

                doc_input.fill(documento)

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
                raise SourceError("co.rethus", f"Query failed: {e}") from e

    def _parse_result(self, page, documento: str) -> RethusResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        esta_registrado = any(phrase in body_lower for phrase in [
            "registrado",
            "activo",
            "resultado de la consulta",
        ])

        no_registrado = any(phrase in body_lower for phrase in [
            "no se encontr",
            "no registra",
            "sin resultados",
        ])

        if no_registrado:
            esta_registrado = False

        nombre = ""
        profesion = ""
        numero_registro = ""
        estado_registro = ""
        fecha_registro = ""
        universidad = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if "nombre" in lower and ":" in stripped:
                nombre = stripped.split(":", 1)[1].strip()
            elif ("profesi" in lower or "título" in lower) and ":" in stripped:
                profesion = stripped.split(":", 1)[1].strip()
            elif "registro" in lower and "número" in lower and ":" in stripped:
                numero_registro = stripped.split(":", 1)[1].strip()
            elif "estado" in lower and ":" in stripped:
                estado_registro = stripped.split(":", 1)[1].strip()
            elif "fecha" in lower and "registro" in lower and ":" in stripped:
                fecha_registro = stripped.split(":", 1)[1].strip()
            elif "universidad" in lower and ":" in stripped:
                universidad = stripped.split(":", 1)[1].strip()
            elif ("instituci" in lower or "entidad" in lower) and ":" in stripped and not universidad:
                universidad = stripped.split(":", 1)[1].strip()

        estado_msg = "Registrado" if esta_registrado else "No registrado"

        return RethusResult(
            queried_at=datetime.now(),
            documento=documento,
            nombre=nombre,
            esta_registrado=esta_registrado,
            profesion=profesion,
            numero_registro=numero_registro,
            estado_registro=estado_registro,
            fecha_registro=fecha_registro,
            universidad=universidad,
            mensaje=f"RETHUS {documento}: {estado_msg}",
        )
