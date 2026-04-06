"""Professional council verification source — Colombia.

Queries COPNIA and other professional councils for license verification.

URL: https://www.copnia.gov.co/
Input: document number (cedula)
Returns: professional license status
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.consejo_profesional import ConsejoProfesionalResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CONSEJO_URL = (
    "https://tramites.copnia.gov.co/Copnia_Microsite/CertificateOfGoodStanding/"
    "CertificateOfGoodStandingStart"
)


@register
class ConsejoProfesionalSource(BaseSource):
    """Query professional council license verification by document number."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.consejo_profesional",
            display_name="COPNIA — Consejo Profesional de Ingeniería",
            description="Colombia professional engineering council license verification by cedula",
            country="CO",
            url=CONSEJO_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        documento = input.document_number.strip()
        if not documento:
            raise SourceError("co.consejo_profesional", "Document number is required")
        return self._fetch(documento, audit=input.audit)

    def _fetch(self, documento: str, audit: bool = False) -> ConsejoProfesionalResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying consejo profesional: documento=%s", documento)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(CONSEJO_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)
                page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)
                page.wait_for_timeout(2000)

                doc_input = page.query_selector(
                    "#DocumentNumber, input[name='DocumentNumber'], input[type='text']"
                )
                if doc_input:
                    doc_input.fill(documento)
                    submit = page.query_selector(
                        "#btnConsult, button[type='submit'], input[type='submit']"
                    )
                    if submit:
                        submit.click()
                    else:
                        doc_input.press("Enter")
                    page.wait_for_timeout(4000)

                body_text = page.inner_text("body")
                body_lower = body_text.lower()

                nombre = ""
                profession = ""
                license_status = ""

                for line in body_text.split("\n"):
                    line_stripped = line.strip()
                    line_lower = line_stripped.lower()
                    if "nombre" in line_lower and not nombre:
                        parts = line_stripped.split(":")
                        if len(parts) > 1:
                            nombre = parts[1].strip()
                    if any(k in line_lower for k in ["profesión", "profesion", "título"]):
                        parts = line_stripped.split(":")
                        if len(parts) > 1 and not profession:
                            profession = parts[1].strip()
                    if "estado" in line_lower or "vigente" in line_lower:
                        parts = line_stripped.split(":")
                        if len(parts) > 1 and not license_status:
                            license_status = parts[1].strip()

                if not license_status:
                    if "vigente" in body_lower:
                        license_status = "Vigente"
                    elif "no se encontr" in body_lower or "no registra" in body_lower:
                        license_status = "No encontrado"

            return ConsejoProfesionalResult(
                queried_at=datetime.now(),
                documento=documento,
                nombre=nombre,
                profession=profession,
                license_status=license_status,
                details=f"Consejo profesional query for: {documento}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("co.consejo_profesional", f"Query failed: {e}") from e
