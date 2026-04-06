"""Colombia SENA source — certification/training verification.

Queries SENA portal for certification and training status by document number.
Browser-based, public access.

Source: https://www.sena.edu.co/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.sena import SenaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SENA_URL = "https://certificados.sena.edu.co/CertificadoSena/validarCertificado.aspx"


@register
class SenaSource(BaseSource):
    """Query SENA portal for certification and training verification."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.sena",
            display_name="SENA — Verificación de Certificados",
            description="Colombia SENA certification and training verification by document number",
            country="CO",
            url=SENA_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        documento = input.extra.get("documento", "") or input.document_number
        if not documento:
            raise SourceError("co.sena", "Document number (documento) is required")
        return self._query(documento.strip(), audit=input.audit)

    def _query(self, documento: str, audit: bool = False) -> SenaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("co.sena", "documento", documento)

        with browser.page(SENA_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                doc_input = page.query_selector(
                    'input[id*="documento" i], input[name*="documento" i], '
                    'input[placeholder*="documento" i], input[placeholder*="cédula" i], '
                    'input[type="text"]'
                )
                if not doc_input:
                    raise SourceError("co.sena", "Could not find document input field")

                doc_input.fill(documento)
                logger.info("Filled documento: %s", documento)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'input[value*="Consultar"], button[id*="consultar" i]'
                )
                if submit:
                    submit.click()
                else:
                    doc_input.press("Enter")

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(3000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, documento)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("co.sena", f"Query failed: {e}") from e

    def _parse_result(self, page: object, documento: str) -> SenaResult:
        from datetime import datetime

        body_text = page.inner_text("body")  # type: ignore[union-attr]
        body_lower = body_text.lower()
        nombre = ""
        certification_status = ""
        program = ""
        details: dict[str, str] = {}

        not_found_phrases = ("no se encontr", "no registra", "sin resultado")
        if any(phrase in body_lower for phrase in not_found_phrases):
            return SenaResult(
                queried_at=datetime.now(),
                documento=documento,
            )

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if not stripped:
                continue

            if ":" in stripped:
                key, _, val = stripped.partition(":")
                key_clean = key.strip()
                val_clean = val.strip()
                if val_clean:
                    details[key_clean] = val_clean

                if any(k in lower for k in ("nombre", "aprendiz", "cursante")):
                    if not nombre and val_clean:
                        nombre = val_clean

                if any(k in lower for k in ("programa", "curso", "formación")):
                    if not program and val_clean:
                        program = val_clean

                if any(k in lower for k in ("estado", "certificado", "situación")):
                    if not certification_status and val_clean:
                        certification_status = val_clean

        return SenaResult(
            queried_at=datetime.now(),
            documento=documento,
            nombre=nombre,
            certification_status=certification_status,
            program=program,
            details=details,
        )
