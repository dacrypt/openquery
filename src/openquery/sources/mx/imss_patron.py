"""Mexico IMSS employer registry source.

Queries IMSS digital services portal for employer registration status.
Browser-based.

Source: https://serviciosdigitales.imss.gob.mx/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.mx.imss_patron import ImssPatronResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

IMSS_PATRON_URL = "https://serviciosdigitales.imss.gob.mx/gestionAsegurados-web-externo/asegurado"


@register
class ImssPatronSource(BaseSource):
    """Query IMSS employer registry for registration status."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="mx.imss_patron",
            display_name="IMSS — Registro Patronal",
            description="Mexico IMSS employer registry: employer name and registration status",
            country="MX",
            url=IMSS_PATRON_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        registro = input.extra.get("registro_patronal", "") or input.document_number
        if not registro:
            raise SourceError(
                "mx.imss_patron",
                "Employer registration number is required (pass via extra.registro_patronal)",
            )
        return self._query(registro.strip(), audit=input.audit)

    def _query(self, registro_patronal: str, audit: bool = False) -> ImssPatronResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("mx.imss_patron", "registro_patronal", registro_patronal)

        with browser.page(IMSS_PATRON_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                reg_input = page.query_selector(
                    'input[name*="patron" i], input[id*="patron" i], '
                    'input[name*="registro" i], input[id*="registro" i], '
                    'input[placeholder*="registro" i], input[type="text"]'
                )
                if not reg_input:
                    raise SourceError(
                        "mx.imss_patron", "Could not find employer registration input field"
                    )
                reg_input.fill(registro_patronal)
                logger.info("Filled registro patronal: %s", registro_patronal)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'input[type="submit"], button[type="submit"], '
                    "button:has-text('Consultar'), button:has-text('Buscar')"
                )
                if submit:
                    submit.click()
                else:
                    reg_input.press("Enter")

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(3000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, registro_patronal)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("mx.imss_patron", f"Query failed: {e}") from e

    def _parse_result(self, page, registro_patronal: str) -> ImssPatronResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = ImssPatronResult(
            queried_at=datetime.now(), registro_patronal=registro_patronal
        )
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

            # Employer name
            if any(
                k in lower
                for k in ("razón social", "razon social", "nombre", "patrón", "patron")
            ):
                if ":" in stripped and not result.employer_name:
                    result.employer_name = stripped.split(":", 1)[1].strip()

            # Status
            if any(k in lower for k in ("estado", "estatus", "situación", "situacion", "vigente")):
                if ":" in stripped and not result.status:
                    result.status = stripped.split(":", 1)[1].strip()

        result.details = details
        return result
