"""Guatemala NIT source — SAT tax registry.

Queries Guatemala's Superintendencia de Administración Tributaria (SAT)
for NIT (Número de Identificación Tributaria) data.

Source: https://portal.sat.gob.gt/portal/consulta-cui-nit/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.gt.nit import GtNitResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SAT_URL = "https://portal.sat.gob.gt/portal/consulta-cui-nit/"


@register
class GtNitSource(BaseSource):
    """Query Guatemalan tax registry (SAT) by NIT."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="gt.nit",
            display_name="SAT — Consulta NIT",
            description="Guatemalan tax registry: taxpayer name, status (Superintendencia de Administración Tributaria)",  # noqa: E501
            country="GT",
            url=SAT_URL,
            supported_inputs=[DocumentType.NIT, DocumentType.CUSTOM],
            requires_captcha=True,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        nit = input.extra.get("nit", "") or input.document_number
        if not nit:
            raise SourceError("gt.nit", "NIT is required")
        return self._query(nit.strip(), audit=input.audit)

    def _query(self, nit: str, audit: bool = False) -> GtNitResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("gt.nit", "nit", nit)

        with browser.page(SAT_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                nit_input = page.query_selector(
                    '#nitConsulta, input[id*="nit"], input[name*="nit"], input[type="text"]'
                )
                if not nit_input:
                    raise SourceError("gt.nit", "Could not find NIT input field")

                nit_input.fill(nit)
                logger.info("Filled NIT: %s", nit)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    '#btnConsultar, button[type="submit"], '
                    'input[type="submit"], '
                    'button:has-text("Consultar")'
                )
                if submit:
                    submit.click()
                else:
                    nit_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, nit)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("gt.nit", f"Query failed: {e}") from e

    def _parse_result(self, page, nit: str) -> GtNitResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        result = GtNitResult(queried_at=datetime.now(), nit=nit)

        field_map = {
            "nombre": "nombre",
            "estado": "estado",
            "tipo": "tipo_contribuyente",
            "domicilio": "domicilio_fiscal",
            "departamento": "departamento",
            "municipio": "municipio",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_map.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    setattr(result, field, value)
                    break

        return result
