"""Dominican Republic INTRANT source — driver license status.

Queries INTRANT for driver license status, expiration, and fines.

Source: https://www.intrant.gob.do/categoria/servicios/consulta-en-linea-estatus-de-licencias-de-conducir
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.do.intrant import DoIntrantResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

INTRANT_URL = "https://www.intrant.gob.do/categoria/servicios/consulta-en-linea-estatus-de-licencias-de-conducir"


@register
class DoIntrantSource(BaseSource):
    """Query Dominican Republic INTRANT driver license status."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="do.intrant",
            display_name="INTRANT — Estatus Licencia de Conducir",
            description="Dominican Republic driver license status, expiration, and fines (INTRANT)",
            country="DO",
            url=INTRANT_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_value = input.document_number or input.extra.get("cedula", "")
        if not search_value:
            raise SourceError("do.intrant", "License number or cédula is required")
        return self._query(search_value.strip(), audit=input.audit)

    def _query(self, search_value: str, audit: bool = False) -> DoIntrantResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("do.intrant", "cedula", search_value)

        with browser.page(INTRANT_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[name*="licencia"], input[id*="licencia"], '
                    'input[name*="cedula"], input[id*="cedula"], '
                    'input[placeholder*="licencia"], input[placeholder*="dula"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("do.intrant", "Could not find search input field")

                search_input.fill(search_value)
                logger.info("Filled search value: %s", search_value)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button:has-text("Consultar"), button:has-text("Buscar")'
                )
                if submit:
                    submit.click()
                else:
                    search_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_value)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("do.intrant", f"Query failed: {e}") from e

    def _parse_result(self, page, search_value: str) -> DoIntrantResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = DoIntrantResult(queried_at=datetime.now(), search_value=search_value)

        field_map = {
            "estado": "license_status",
            "status": "license_status",
            "vencimiento": "expiration",
            "expirac": "expiration",
            "multas": "fines_count",
            "total": "total_fines",
        }

        lines = body_text.split("\n")
        for line in lines:
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_map.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value:
                        if field == "fines_count":
                            try:
                                result.fines_count = int(value)
                            except ValueError:
                                pass
                        else:
                            setattr(result, field, value)
                    break

        if body_text.strip():
            result.details = body_text.strip()[:500]

        return result
