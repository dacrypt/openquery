"""INPEC source — Colombian prison population registry.

Queries INPEC for incarceration status of a person by cédula.

Flow:
1. Navigate to INPEC consultation page
2. Enter cédula number
3. Parse result for reclusion status

Source: https://www.inpec.gov.co/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.inpec import InpecResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

INPEC_URL = "https://www.inpec.gov.co/"


@register
class InpecSource(BaseSource):
    """Query Colombian prison population registry (INPEC)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.inpec",
            display_name="INPEC — Población Privada de la Libertad",
            description="Colombian prison population registry lookup",
            country="CO",
            url=INPEC_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CEDULA:
            raise SourceError("co.inpec", f"Only cedula supported, got: {input.document_type}")
        return self._query(input.document_number, audit=input.audit)

    def _query(self, cedula: str, audit: bool = False) -> InpecResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.inpec", "cedula", cedula)

        with browser.page(INPEC_URL) as page:
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
                    raise SourceError("co.inpec", "Could not find cedula input field")

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
                raise SourceError("co.inpec", f"Query failed: {e}") from e

    def _parse_result(self, page, cedula: str) -> InpecResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        esta_recluido = any(phrase in body_lower for phrase in [
            "privado de la libertad",
            "recluido",
            "interno",
            "se encuentra",
        ])

        no_recluido = any(phrase in body_lower for phrase in [
            "no se encuentra",
            "no registra",
            "sin resultados",
        ])

        if no_recluido:
            esta_recluido = False

        nombre = ""
        centro_reclusion = ""
        situacion_juridica = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if "nombre" in lower and ":" in stripped:
                nombre = stripped.split(":", 1)[1].strip()
            elif ("centro" in lower or "establecimiento" in lower) and ":" in stripped:
                centro_reclusion = stripped.split(":", 1)[1].strip()
            elif ("situaci" in lower or "jurídica" in lower) and ":" in stripped:
                situacion_juridica = stripped.split(":", 1)[1].strip()

        estado_msg = "Recluido" if esta_recluido else "No registra"

        return InpecResult(
            queried_at=datetime.now(),
            cedula=cedula,
            nombre=nombre,
            esta_recluido=esta_recluido,
            centro_reclusion=centro_reclusion,
            situacion_juridica=situacion_juridica,
            mensaje=f"INPEC {cedula}: {estado_msg}",
        )
