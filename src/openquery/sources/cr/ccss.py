"""Costa Rica CCSS social security source.

Queries CCSS (Caja Costarricense de Seguro Social) for social security
affiliation status by cedula.

URL: https://www.ccss.sa.cr/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.cr.ccss import CcssResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CCSS_URL = "https://www.ccss.sa.cr/"


@register
class CcssSource(BaseSource):
    """Query Costa Rica CCSS social security affiliation."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="cr.ccss",
            display_name="CCSS — Seguro Social (CR)",
            description="Costa Rica CCSS social security affiliation status by cedula",
            country="CR",
            url=CCSS_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        cedula = input.extra.get("cedula", "") or input.document_number
        if not cedula:
            raise SourceError("cr.ccss", "Cedula is required")
        return self._query(cedula.strip(), audit=input.audit)

    def _query(self, cedula: str, audit: bool = False) -> CcssResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("cr.ccss", "cedula", cedula)

        with browser.page(CCSS_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                cedula_input = page.query_selector(
                    "input[name*='cedula'], input[id*='cedula'], "
                    "input[name*='identificacion'], input[type='text']"
                )
                if not cedula_input:
                    raise SourceError("cr.ccss", "Could not find cedula input field")

                cedula_input.fill(cedula)
                logger.info("Filled cedula: %s", cedula)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    "button[type='submit'], input[type='submit'], button[id*='buscar'], button[id*='consultar']"
                )
                if submit:
                    submit.click()
                else:
                    cedula_input.press("Enter")

                page.wait_for_timeout(3000)
                page.wait_for_selector(
                    "table, .resultado, .result, #resultado, .asegurado",
                    timeout=15000,
                )

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, cedula)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("cr.ccss", f"Query failed: {e}") from e

    def _parse_result(self, page, cedula: str) -> CcssResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = CcssResult(queried_at=datetime.now(), cedula=cedula)

        field_patterns = {
            "estado": "affiliation_status",
            "afiliacion": "affiliation_status",
            "asegurado": "affiliation_status",
            "condicion": "affiliation_status",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_patterns.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value:
                        setattr(result, field, value)
                    break

        rows = page.query_selector_all("table tr")
        if len(rows) >= 2:
            cells = rows[1].query_selector_all("td")
            if cells:
                values = [(c.inner_text() or "").strip() for c in cells]
                if len(values) >= 1 and not result.affiliation_status:
                    result.affiliation_status = values[0]

        return result
