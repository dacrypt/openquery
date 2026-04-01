"""Libreta Militar source — Colombian military service status.

Queries the military service status / libreta militar.

Flow:
1. Navigate to consultation page
2. Enter document number
3. Submit and parse result

Source: https://www.libretamilitar.mil.co/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.libreta_militar import LibretaMilitarResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

LIBRETA_URL = "https://www.libretamilitar.mil.co/"


@register
class LibretaMilitarSource(BaseSource):
    """Query Colombian military service status (Libreta Militar)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.libreta_militar",
            display_name="Ejército — Libreta Militar",
            description="Colombian military service card / situation status",
            country="CO",
            url=LIBRETA_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CEDULA:
            raise SourceError("co.libreta_militar", f"Only cedula supported, got: {input.document_type}")
        return self._query(input.document_number, audit=input.audit)

    def _query(self, documento: str, audit: bool = False) -> LibretaMilitarResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.libreta_militar", "cedula", documento)

        with browser.page(LIBRETA_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_selector('input[type="text"]', timeout=15000)
                page.wait_for_timeout(2000)

                # Fill document
                doc_input = page.query_selector(
                    'input[type="text"][id*="documento"], '
                    'input[type="text"][id*="cedula"], '
                    'input[type="text"][id*="numero"], '
                    'input[type="text"]'
                )
                if not doc_input:
                    raise SourceError("co.libreta_militar", "Could not find document input field")

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
                raise SourceError("co.libreta_militar", f"Query failed: {e}") from e

    def _parse_result(self, page, documento: str) -> LibretaMilitarResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        situacion = "Desconocida"
        if "definida" in body_lower and "no definida" not in body_lower:
            situacion = "Definida"
        elif "no definida" in body_lower:
            situacion = "No definida"

        nombre = ""
        clase = ""
        numero = ""
        distrito = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if "nombre" in lower and ":" in stripped:
                nombre = stripped.split(":", 1)[1].strip()
            elif "clase" in lower and ":" in stripped:
                clase = stripped.split(":", 1)[1].strip()
            elif "número" in lower and "libreta" in lower and ":" in stripped:
                numero = stripped.split(":", 1)[1].strip()
            elif "distrito" in lower and ":" in stripped:
                distrito = stripped.split(":", 1)[1].strip()

        return LibretaMilitarResult(
            queried_at=datetime.now(),
            documento=documento,
            tipo_documento="cedula",
            nombre=nombre,
            situacion_militar=situacion,
            clase_libreta=clase,
            numero_libreta=numero,
            distrito_militar=distrito,
            mensaje=f"Situación militar: {situacion}",
        )
