"""Professional registration source — Argentina.

Queries professional councils for registration status by number.

URL: varies by council
Input: registration number (custom)
Returns: professional license status
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ar.matricula_profesional import MatriculaProfesionalResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

MATRICULA_URL = "https://www.cpacf.org.ar/consultas/matriculados"


@register
class MatriculaProfesionalSource(BaseSource):
    """Query Argentina professional registration by matricula number."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ar.matricula_profesional",
            display_name="CPACF — Matrícula Profesional Argentina",
            description="Argentina professional council registration lookup by matricula number",
            country="AR",
            url=MATRICULA_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("registration_number", input.document_number).strip()
        if not search_term:
            raise SourceError(
                "ar.matricula_profesional",
                "Provide a registration number (extra.registration_number or document_number)",
            )
        return self._fetch(search_term, audit=input.audit)

    def _fetch(self, search_term: str, audit: bool = False) -> MatriculaProfesionalResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying matricula profesional: search_term=%s", search_term)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(MATRICULA_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)  # noqa: E501
                page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                search_input = page.query_selector(
                    "input[name*='matricula'], input[id*='matricula'], "
                    "input[placeholder*='matrícula' i], input[type='text']"
                )
                if search_input:
                    search_input.fill(search_term)
                    submit = page.query_selector("button[type='submit'], input[type='submit']")
                    if submit:
                        submit.click()
                    else:
                        search_input.press("Enter")
                    page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

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
                    if any(k in line_lower for k in ["profesión", "especialidad", "título"]):
                        parts = line_stripped.split(":")
                        if len(parts) > 1 and not profession:
                            profession = parts[1].strip()
                    if "estado" in line_lower or "matriculado" in line_lower:
                        parts = line_stripped.split(":")
                        if len(parts) > 1 and not license_status:
                            license_status = parts[1].strip()

                if not license_status:
                    if "vigente" in body_lower or "activo" in body_lower:
                        license_status = "Vigente"
                    elif "no encontr" in body_lower:
                        license_status = "No encontrado"

            return MatriculaProfesionalResult(
                queried_at=datetime.now(),
                search_term=search_term,
                nombre=nombre,
                profession=profession,
                license_status=license_status,
                details=f"Matricula profesional query for: {search_term}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("ar.matricula_profesional", f"Query failed: {e}") from e
