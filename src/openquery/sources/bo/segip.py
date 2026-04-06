"""SEGIP source — Bolivia identity service lookup.

Queries Bolivia's SEGIP (Servicio General de Identificación Personal)
for identity status and document validity by CI number.

Source: https://www.segip.gob.bo/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.bo.segip import SegipResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SEGIP_URL = "https://www.segip.gob.bo/"


@register
class SegipSource(BaseSource):
    """Query Bolivia SEGIP identity service by CI number."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="bo.segip",
            display_name="SEGIP — Servicio de Identificación Personal",
            description=(
                "Bolivia SEGIP identity service: identity status and document validity by CI number"
            ),
            country="BO",
            url=SEGIP_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        ci = input.extra.get("ci", "") or input.document_number.strip()
        if not ci:
            raise SourceError("bo.segip", "CI number is required")
        return self._query(ci=ci, audit=input.audit)

    def _query(self, ci: str, audit: bool = False) -> SegipResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("bo.segip", "ci", ci)

        with browser.page(SEGIP_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "page_loaded")

                ci_input = page.query_selector(
                    'input[name*="ci"], input[name*="cedula"], '
                    'input[id*="ci"], input[id*="cedula"], '
                    'input[placeholder*="CI"], input[placeholder*="cédula"], '
                    'input[type="text"]'
                )
                if not ci_input:
                    raise SourceError("bo.segip", "Could not find CI input field")

                ci_input.fill(ci)
                logger.info("Querying SEGIP for CI: %s", ci)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit_btn = page.query_selector(
                    'input[type="submit"], button[type="submit"], '
                    'button:has-text("Consultar"), button:has-text("Buscar"), '
                    'input[value*="Consultar"], input[value*="Buscar"]'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    ci_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, ci)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("bo.segip", f"Query failed: {e}") from e

    def _parse_result(self, page, ci: str) -> SegipResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        nombre = ""
        document_status = ""

        field_map = {
            "nombre": "nombre",
            "apellido": "nombre",
            "estado": "document_status",
            "estatus": "document_status",
            "vigencia": "document_status",
            "válido": "document_status",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_map.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value:
                        if field == "nombre" and not nombre:
                            nombre = value
                        elif field == "document_status" and not document_status:
                            document_status = value
                    break

        return SegipResult(
            queried_at=datetime.now(),
            ci=ci,
            nombre=nombre,
            document_status=document_status,
            details=body_text.strip()[:500],
        )
