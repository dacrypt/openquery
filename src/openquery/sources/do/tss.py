"""Dominican Republic TSS social security affiliation source.

Queries TSS (Sistema de Seguridad Social) for affiliation status, employer,
ARS (health insurer), and AFP (pension fund) by cedula.

URL: https://www.tss.gob.do/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.do.tss import TssResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

TSS_URL = "https://www.tss.gob.do/"


@register
class TssSource(BaseSource):
    """Query Dominican Republic TSS social security affiliation."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="do.tss",
            display_name="TSS — Seguridad Social (RD)",
            description="Dominican Republic TSS social security affiliation: employer, ARS, AFP",
            country="DO",
            url=TSS_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        cedula = input.extra.get("cedula", "") or input.document_number
        if not cedula:
            raise SourceError("do.tss", "Cedula is required")
        return self._query(cedula.strip(), audit=input.audit)

    def _query(self, cedula: str, audit: bool = False) -> TssResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("do.tss", "cedula", cedula)

        with browser.page(TSS_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill cedula input
                cedula_input = page.query_selector(
                    "input[name*='cedula'], input[id*='cedula'], input[type='text']"
                )
                if not cedula_input:
                    raise SourceError("do.tss", "Could not find cedula input field")

                cedula_input.fill(cedula)
                logger.info("Filled cedula: %s", cedula)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit form
                submit = page.query_selector(
                    "button[type='submit'], input[type='submit'], button[id*='buscar'], button[id*='consultar']"  # noqa: E501
                )
                if submit:
                    submit.click()
                else:
                    cedula_input.press("Enter")

                page.wait_for_timeout(3000)
                page.wait_for_selector(
                    "table, .resultado, .result, #resultado, .afiliado",
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
                raise SourceError("do.tss", f"Query failed: {e}") from e

    def _parse_result(self, page, cedula: str) -> TssResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = TssResult(queried_at=datetime.now(), cedula=cedula)

        field_patterns = {
            "estado": "affiliation_status",
            "afiliacion": "affiliation_status",
            "empleador": "employer",
            "empresa": "employer",
            "ars": "ars",
            "afp": "afp",
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

        # Try table rows
        rows = page.query_selector_all("table tr")
        if len(rows) >= 2:
            cells = rows[1].query_selector_all("td")
            if cells:
                values = [(c.inner_text() or "").strip() for c in cells]
                if len(values) >= 1 and not result.affiliation_status:
                    result.affiliation_status = values[0]
                if len(values) >= 2 and not result.employer:
                    result.employer = values[1]
                if len(values) >= 3 and not result.ars:
                    result.ars = values[2]
                if len(values) >= 4 and not result.afp:
                    result.afp = values[3]

        return result
