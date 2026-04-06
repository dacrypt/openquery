"""Uruguay DGI source — tax/RUT lookup.

Queries Uruguay's Dirección General Impositiva for contributor
status, RUT validity, and tax compliance by RUT (12-digit).

Source: https://servicios.dgi.gub.uy/serviciosenlinea
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.uy.dgi import UyDgiResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

DGI_URL = "https://servicios.dgi.gub.uy/serviciosenlinea"


@register
class UyDgiSource(BaseSource):
    """Query Uruguayan DGI contributor status and tax compliance by RUT."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="uy.dgi",
            display_name="DGI — Consulta de RUT",
            description="Uruguay contributor status, RUT validity, tax compliance (Dirección General Impositiva)",  # noqa: E501
            country="UY",
            url=DGI_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        rut = input.document_number or input.extra.get("rut", "")
        if not rut:
            raise SourceError("uy.dgi", "RUT (12-digit) is required")
        return self._query(rut.strip(), audit=input.audit)

    def _query(self, rut: str, audit: bool = False) -> UyDgiResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("uy.dgi", "custom", rut)

        with browser.page(DGI_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                rut_input = page.query_selector(
                    'input[name*="rut"], input[id*="rut"], '
                    'input[name*="contribuyente"], input[id*="contribuyente"], '
                    'input[type="text"]'
                )
                if not rut_input:
                    raise SourceError("uy.dgi", "Could not find RUT input field")

                rut_input.fill(rut)
                logger.info("Filled RUT: %s", rut)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button:has-text("Buscar"), button:has-text("Consultar")'
                )
                if submit:
                    submit.click()
                else:
                    rut_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, rut)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("uy.dgi", f"Query failed: {e}") from e

    def _parse_result(self, page, rut: str) -> UyDgiResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = UyDgiResult(queried_at=datetime.now(), rut=rut)

        field_map = {
            "estado": "contributor_status",
            "situacion": "contributor_status",
            "rut": "rut_valid",
            "valido": "rut_valid",
            "cumplimiento": "tax_compliance",
            "obligaciones": "tax_compliance",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_map.items():
                if label in lower and (":" in stripped or "\t" in stripped):
                    sep = ":" if ":" in stripped else "\t"
                    value = stripped.split(sep, 1)[1].strip()
                    if value and not getattr(result, field):
                        setattr(result, field, value)
                    break

        if body_text.strip():
            result.details = body_text.strip()[:500]

        return result
