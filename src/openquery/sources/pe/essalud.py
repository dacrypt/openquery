"""Peru EsSalud source — health insurance affiliation lookup.

Queries EsSalud SISEP portal for affiliation status and employer by DNI.
Browser-based.

Source: https://ww1.essalud.gob.pe/sisep/postulante/postulante_acredita.htm
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pe.essalud import EssaludResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

ESSALUD_URL = "https://ww1.essalud.gob.pe/sisep/postulante/postulante_acredita.htm"


@register
class EssaludSource(BaseSource):
    """Query EsSalud SISEP for health insurance affiliation status."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pe.essalud",
            display_name="EsSalud — Acreditación de Afiliado",
            description="Peru EsSalud health insurance: affiliation status and employer by DNI",
            country="PE",
            url=ESSALUD_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        dni = input.document_number or input.extra.get("dni", "")
        if not dni:
            raise SourceError("pe.essalud", "DNI is required")
        return self._query(dni.strip(), audit=input.audit)

    def _query(self, dni: str, audit: bool = False) -> EssaludResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("pe.essalud", "cedula", dni)

        with browser.page(ESSALUD_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                dni_input = page.query_selector(
                    'input[name*="dni" i], input[id*="dni" i], '
                    'input[placeholder*="dni" i], input[name*="documento" i], '
                    'input[type="text"]'
                )
                if not dni_input:
                    raise SourceError("pe.essalud", "Could not find DNI input field")

                dni_input.fill(dni)
                logger.info("Filled DNI: %s", dni)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'input[type="submit"], button[type="submit"], '
                    "button:has-text('Consultar'), button:has-text('Buscar'), "
                    "button:has-text('Acreditar')"
                )
                if submit:
                    submit.click()
                else:
                    dni_input.press("Enter")

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(3000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, dni)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("pe.essalud", f"Query failed: {e}") from e

    def _parse_result(self, page, dni: str) -> EssaludResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = EssaludResult(queried_at=datetime.now(), dni=dni)
        details: dict[str, str] = {}

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if not stripped:
                continue

            if ":" in stripped:
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip()
                if key and val:
                    details[key] = val

            # Affiliation status
            if any(k in lower for k in ("estado", "afiliación", "afiliacion", "acreditado")):
                if ":" in stripped and not result.affiliation_status:
                    result.affiliation_status = stripped.split(":", 1)[1].strip()

            # Employer
            if any(k in lower for k in ("empleador", "empresa", "entidad empleadora")):
                if ":" in stripped and not result.employer:
                    result.employer = stripped.split(":", 1)[1].strip()

        result.details = details
        return result
