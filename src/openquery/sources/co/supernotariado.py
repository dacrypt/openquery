"""Supernotariado source — Colombian notary registry.

Queries the Superintendencia de Notariado y Registro for notary
and registry information.

Source: https://www.supernotariado.gov.co/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.supernotariado import SupernotariadoResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SUPERNOTARIADO_URL = "https://www.supernotariado.gov.co/servicios/notariado/lista-de-notarias/"


@register
class SupernotariadoSource(BaseSource):
    """Query Colombian notary registry (Supernotariado)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.supernotariado",
            display_name="Supernotariado — Registro de Notarías",
            description="Colombian notary registry: notary details, city, and status (Supernotariado)",  # noqa: E501
            country="CO",
            url=SUPERNOTARIADO_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (
            input.extra.get("notary_name", "")
            or input.extra.get("name", "")
            or input.document_number
        ).strip()
        if not search_term:
            raise SourceError("co.supernotariado", "Notary name required (pass via extra.notary_name or document_number)")  # noqa: E501
        return self._query(search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> SupernotariadoResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.supernotariado", "notary", search_term)

        with browser.page(SUPERNOTARIADO_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(2000)

                search_input = page.locator(
                    'input[placeholder*="buscar"], input[placeholder*="Buscar"], '
                    'input[type="text"], input[type="search"]'
                ).first
                if search_input:
                    search_input.fill(search_term)
                    logger.info("Searching Supernotariado for: %s", search_term)
                    page.wait_for_timeout(1500)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_term)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("co.supernotariado", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> SupernotariadoResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = SupernotariadoResult(queried_at=datetime.now(), search_term=search_term)

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if "notaría" in lower and ":" in stripped and not result.notary_name:
                result.notary_name = stripped.split(":", 1)[1].strip()
            elif "ciudad" in lower and ":" in stripped and not result.city:
                result.city = stripped.split(":", 1)[1].strip()
            elif "estado" in lower and ":" in stripped and not result.status:
                result.status = stripped.split(":", 1)[1].strip()

        return result
