"""MSP Profesionales source — Uruguayan health professionals registry.

Queries the MSP (Ministerio de Salud Publica) for health professional registrations.

Flow:
1. Navigate to MSP consultation page
2. Enter professional name
3. Parse result for profession, registration status

Source: https://www.gub.uy/ministerio-salud-publica/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.uy.msp_profesionales import MspProfesionalesResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

MSP_UY_URL = "https://www.gub.uy/ministerio-salud-publica/tramites-y-servicios/servicios/registro-profesionales-salud"


@register
class MspProfesionalesSource(BaseSource):
    """Query Uruguayan health professionals registry (MSP)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="uy.msp_profesionales",
            display_name="MSP Uruguay — Profesionales de Salud",
            description="Uruguayan health professionals registration (MSP)",
            country="UY",
            url=MSP_UY_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("professional_name") or input.document_number
        if not search_term:
            raise SourceError("uy.msp_profesionales", "professional_name is required")
        return self._query(search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> MspProfesionalesResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("uy.msp_profesionales", "custom", search_term)

        with browser.page(MSP_UY_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[type="text"], input[type="search"], '
                    'input[id*="nombre"], input[id*="buscar"]'
                )
                if not search_input:
                    raise SourceError("uy.msp_profesionales", "Could not find search input field")

                search_input.fill(search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="buscar"]'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    search_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_term)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("uy.msp_profesionales", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> MspProfesionalesResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        professional_name = ""
        profession = ""
        registration_status = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if not stripped:
                continue
            if "nombre" in lower and ":" in stripped:
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not professional_name:
                    professional_name = parts[1].strip()
            elif ("profesi" in lower or "especialidad" in lower or "titulo" in lower) and ":" in stripped:  # noqa: E501
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

        return MspProfesionalesResult(
            queried_at=datetime.now(),
            search_term=search_term,
            professional_name=professional_name,
            profession=profession,
            registration_status=registration_status,
            details={"found": found},
        )
