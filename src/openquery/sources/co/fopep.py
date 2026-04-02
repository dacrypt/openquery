"""FOPEP source — Colombian pensioners payroll lookup.

Queries FOPEP (Fondo de Pensiones Públicas) for pension payroll status.

Flow:
1. Navigate to FOPEP consultation page
2. Enter cédula number
3. Parse result for pension status, entity, type

Source: https://www.fopep.gov.co/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.fopep import FopepResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

FOPEP_URL = "https://www.fopep.gov.co/"


@register
class FopepSource(BaseSource):
    """Query Colombian pensioners payroll (FOPEP)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.fopep",
            display_name="FOPEP — Nómina de Pensionados",
            description="Colombian pensioners payroll lookup (FOPEP)",
            country="CO",
            url=FOPEP_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CEDULA:
            raise SourceError("co.fopep", f"Only cedula supported, got: {input.document_type}")
        return self._query(input.document_number, audit=input.audit)

    def _query(self, cedula: str, audit: bool = False) -> FopepResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.fopep", "cedula", cedula)

        with browser.page(FOPEP_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill cedula
                cedula_input = page.query_selector(
                    'input[type="text"][id*="cedula"], '
                    'input[type="text"][id*="documento"], '
                    'input[type="text"][id*="numero"], '
                    'input[type="text"]'
                )
                if not cedula_input:
                    raise SourceError("co.fopep", "Could not find cedula input field")

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
                raise SourceError("co.fopep", f"Query failed: {e}") from e

    def _parse_result(self, page, cedula: str) -> FopepResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        esta_en_nomina = any(phrase in body_lower for phrase in [
            "en nómina",
            "pensionado activo",
            "se encuentra",
            "registra pensión",
        ])

        no_en_nomina = any(phrase in body_lower for phrase in [
            "no se encuentra",
            "no registra",
            "sin resultados",
            "no está",
        ])

        if no_en_nomina:
            esta_en_nomina = False

        nombre = ""
        entidad_pagadora = ""
        tipo_pension = ""
        estado = "No registrado"

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if "nombre" in lower and ":" in stripped:
                nombre = stripped.split(":", 1)[1].strip()
            elif "entidad" in lower and ":" in stripped:
                entidad_pagadora = stripped.split(":", 1)[1].strip()
            elif ("tipo" in lower and "pensi" in lower) and ":" in stripped:
                tipo_pension = stripped.split(":", 1)[1].strip()
            elif "estado" in lower and ":" in stripped:
                estado = stripped.split(":", 1)[1].strip()

        if esta_en_nomina and estado == "No registrado":
            estado = "En nómina"

        return FopepResult(
            queried_at=datetime.now(),
            cedula=cedula,
            nombre=nombre,
            esta_en_nomina=esta_en_nomina,
            entidad_pagadora=entidad_pagadora,
            tipo_pension=tipo_pension,
            estado=estado,
            mensaje=f"FOPEP {cedula}: {estado}",
        )
