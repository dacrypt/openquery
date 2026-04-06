"""Mexico COFEPRIS source — health product sanitary registry.

Queries COFEPRIS portal for sanitary registration status by product name.
Browser-based.

Source: https://www.gob.mx/cofepris
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.mx.cofepris import CofeprisResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

COFEPRIS_URL = "https://www.gob.mx/cofepris/acciones-y-programas/consulta-de-registros-sanitarios"


@register
class CofeprisSource(BaseSource):
    """Query COFEPRIS for health product sanitary registration status."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="mx.cofepris",
            display_name="COFEPRIS — Registros Sanitarios",
            description="Mexico COFEPRIS health product sanitary registry: product name and registration status",  # noqa: E501
            country="MX",
            url=COFEPRIS_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("search_term", "") or input.document_number
        if not search_term:
            raise SourceError(
                "mx.cofepris",
                "Product name or search term is required (pass via extra.search_term)",
            )
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> CofeprisResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("mx.cofepris", "search_term", search_term)

        with browser.page(COFEPRIS_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[name*="producto" i], input[id*="producto" i], '
                    'input[name*="search" i], input[id*="search" i], '
                    'input[placeholder*="producto" i], input[placeholder*="buscar" i], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("mx.cofepris", "Could not find product search input field")
                search_input.fill(search_term)
                logger.info("Filled search term: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'input[type="submit"], button[type="submit"], '
                    "button:has-text('Buscar'), button:has-text('Consultar')"
                )
                if submit:
                    submit.click()
                else:
                    search_input.press("Enter")

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(3000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_term)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("mx.cofepris", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> CofeprisResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = CofeprisResult(queried_at=datetime.now(), search_term=search_term)
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

            # Product name
            if any(k in lower for k in ("denominación", "denominacion", "producto", "nombre")):
                if ":" in stripped and not result.product_name:
                    result.product_name = stripped.split(":", 1)[1].strip()

            # Registration number
            if any(k in lower for k in ("registro", "número de registro", "folio")):
                if ":" in stripped and not result.registration_number:
                    result.registration_number = stripped.split(":", 1)[1].strip()

            # Status
            if any(k in lower for k in ("estado", "estatus", "vigente", "vencido")):
                if ":" in stripped and not result.status:
                    result.status = stripped.split(":", 1)[1].strip()

        result.details = details
        return result
