"""SENA Egresados source — SENA graduate verification.

Queries the SENA (Servicio Nacional de Aprendizaje) for graduate
and training completion records.

Source: https://www.sena.edu.co/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.sena_egresados import SenaEgresadosResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SENA_EGRESADOS_URL = "https://oferta.senasofiaplus.edu.co/sofia-oferta/cert/certificado-estudio.html"


@register
class SenaEgresadosSource(BaseSource):
    """Query SENA graduate and training completion records."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.sena_egresados",
            display_name="SENA — Verificación de Egresados",
            description="SENA graduate verification: training programs and completion status",
            country="CO",
            url=SENA_EGRESADOS_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        documento = input.document_number.strip()
        if not documento:
            raise SourceError("co.sena_egresados", "Document number (cédula) required")
        return self._query(documento, audit=input.audit)

    def _query(self, documento: str, audit: bool = False) -> SenaEgresadosResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.sena_egresados", "cedula", documento)

        with browser.page(SENA_EGRESADOS_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(2000)

                doc_input = page.locator(
                    'input[name*="documento"], input[name*="cedula"], '
                    'input[id*="documento"], input[type="text"]'
                ).first
                if doc_input:
                    doc_input.fill(documento)
                    logger.info("Querying SENA Egresados for document: %s", documento[:4] + "***")

                    submit_btn = page.locator('button[type="submit"], input[type="submit"], button:has-text("Consultar")').first  # noqa: E501
                    if submit_btn:
                        submit_btn.click()
                    else:
                        doc_input.press("Enter")

                    page.wait_for_timeout(4000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, documento)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("co.sena_egresados", f"Query failed: {e}") from e

    def _parse_result(self, page, documento: str) -> SenaEgresadosResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = SenaEgresadosResult(queried_at=datetime.now(), documento=documento)

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if "nombre" in lower and ":" in stripped and not result.nombre:
                result.nombre = stripped.split(":", 1)[1].strip()
            elif "programa" in lower and ":" in stripped and not result.program:
                result.program = stripped.split(":", 1)[1].strip()
            elif "estado" in lower and ":" in stripped and not result.completion_status:
                result.completion_status = stripped.split(":", 1)[1].strip()

        return result
