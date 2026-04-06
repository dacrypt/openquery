"""SISA Profesionales source — Argentine health professionals registry.

Queries SISA (Sistema Integrado de Informacion Sanitaria Argentina)
for health professional registration status.

Flow:
1. Navigate to SISA consultation page
2. Enter document number
3. Parse result for profession, registration status

Source: https://sisa.msal.gov.ar/sisa/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ar.sisa_profesionales import SisaProfesionalesResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SISA_URL = "https://sisa.msal.gov.ar/sisa/#sisa"


@register
class SisaProfesionalesSource(BaseSource):
    """Query Argentine health professionals registry (SISA)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ar.sisa_profesionales",
            display_name="SISA — Profesionales de Salud",
            description="Argentine health professionals registration (SISA)",
            country="AR",
            url=SISA_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CEDULA:
            raise SourceError("ar.sisa_profesionales", "Only cedula/DNI supported")
        return self._query(input.document_number, audit=input.audit)

    def _query(self, documento: str, audit: bool = False) -> SisaProfesionalesResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("ar.sisa_profesionales", "cedula", documento)

        with browser.page(SISA_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                doc_input = page.query_selector(
                    'input[type="text"][id*="documento"], '
                    'input[type="text"][id*="dni"], '
                    'input[type="text"]'
                )
                if not doc_input:
                    raise SourceError("ar.sisa_profesionales", "Could not find document input")

                doc_input.fill(documento)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="buscar"], button[id*="consultar"]'
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
                raise SourceError("ar.sisa_profesionales", f"Query failed: {e}") from e

    def _parse_result(self, page, documento: str) -> SisaProfesionalesResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        nombre = ""
        profession = ""
        registration_status = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if not stripped:
                continue
            if "nombre" in lower and ":" in stripped:
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not nombre:
                    nombre = parts[1].strip()
            elif ("profesi" in lower or "especialidad" in lower) and ":" in stripped:
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not profession:
                    profession = parts[1].strip()
            elif "estado" in lower and ":" in stripped:
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not registration_status:
                    registration_status = parts[1].strip()

        found = any(
            phrase in body_lower
            for phrase in ["registrado", "habilitado", "activo", "profesional"]
        )

        if not registration_status:
            registration_status = "Registrado" if found else "No encontrado"

        return SisaProfesionalesResult(
            queried_at=datetime.now(),
            documento=documento,
            nombre=nombre,
            profession=profession,
            registration_status=registration_status,
            details={"found": found},
        )
