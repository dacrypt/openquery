"""El Salvador SSC social security (AFP/ISSS) source.

Queries SSC (Superintendencia del Sistema Financiero) for social security
affiliation status, AFP, and ISSS by DUI.

URL: https://www.ssc.gob.sv/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.sv.ssc import SscResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SSC_URL = "https://www.ssc.gob.sv/"


@register
class SscSource(BaseSource):
    """Query El Salvador SSC social security affiliation."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="sv.ssc",
            display_name="SSC — Seguridad Social (SV)",
            description="El Salvador social security affiliation: AFP and ISSS status by DUI",
            country="SV",
            url=SSC_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        dui = input.extra.get("dui", "") or input.document_number
        if not dui:
            raise SourceError("sv.ssc", "DUI is required")
        return self._query(dui.strip(), audit=input.audit)

    def _query(self, dui: str, audit: bool = False) -> SscResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("sv.ssc", "dui", dui)

        with browser.page(SSC_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                dui_input = page.query_selector(
                    "input[name*='dui'], input[id*='dui'], "
                    "input[name*='cedula'], input[type='text']"
                )
                if not dui_input:
                    raise SourceError("sv.ssc", "Could not find DUI input field")

                dui_input.fill(dui)
                logger.info("Filled DUI: %s", dui)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    "button[type='submit'], input[type='submit'], button[id*='buscar'], button[id*='consultar']"  # noqa: E501
                )
                if submit:
                    submit.click()
                else:
                    dui_input.press("Enter")

                page.wait_for_timeout(3000)
                page.wait_for_selector(
                    "table, .resultado, .result, #resultado, .afiliacion",
                    timeout=15000,
                )

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, dui)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("sv.ssc", f"Query failed: {e}") from e

    def _parse_result(self, page, dui: str) -> SscResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = SscResult(queried_at=datetime.now(), dui=dui)

        field_patterns = {
            "estado": "affiliation_status",
            "afiliacion": "affiliation_status",
            "afp": "afp",
            "isss": "isss",
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
                if len(values) >= 2 and not result.afp:
                    result.afp = values[1]
                if len(values) >= 3 and not result.isss:
                    result.isss = values[2]

        return result
