"""IESS source — Ecuador social security affiliation lookup.

Queries Ecuador's IESS for affiliation status and employer data by cedula.

Flow:
1. Navigate to the IESS consultation page
2. Enter cedula number
3. Submit and parse result

Source: https://www.iess.gob.ec/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ec.iess import IessResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

IESS_URL = "https://www.iess.gob.ec/"


@register
class IessSource(BaseSource):
    """Query Ecuador IESS social security affiliation status."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ec.iess",
            display_name="IESS — Instituto Ecuatoriano de Seguridad Social",
            description="Ecuador social security affiliation status and employer by cedula",
            country="EC",
            url=IESS_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        cedula = input.document_number or input.extra.get("cedula", "")
        if not cedula:
            raise SourceError("ec.iess", "Must provide document_number (cedula)")
        return self._query(cedula=cedula, audit=input.audit)

    def _query(self, cedula: str, audit: bool = False) -> IessResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("ec.iess", "cedula", cedula)

        with browser.page(IESS_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                cedula_input = page.query_selector(
                    'input[id*="cedula"], input[name*="cedula"], '
                    'input[id*="identificacion"], input[name*="identificacion"], '
                    'input[placeholder*="cedula" i], input[type="text"]'
                )
                if cedula_input:
                    cedula_input.fill(cedula)
                    logger.info("Filled cedula: %s", cedula)
                else:
                    raise SourceError("ec.iess", "Cedula input field not found")

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button:has-text("Consultar"), button:has-text("Buscar")'
                )
                if submit:
                    submit.click()
                else:
                    page.keyboard.press("Enter")

                page.wait_for_timeout(4000)
                page.wait_for_selector("body", timeout=15000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, cedula)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("ec.iess", f"Query failed: {e}") from e

    def _parse_result(self, page, cedula: str) -> IessResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = IessResult(queried_at=datetime.now(), cedula=cedula)
        details: dict = {}

        rows = page.query_selector_all("table tr, .result tr")
        for row in rows:
            cells = row.query_selector_all("td, th")
            if len(cells) >= 2:
                label = (cells[0].inner_text() or "").strip()
                value = (cells[1].inner_text() or "").strip()
                if label and value:
                    details[label] = value
                    label_lower = label.lower()
                    if "estado" in label_lower and "afili" in label_lower:
                        result.affiliation_status = value
                    elif "empleador" in label_lower or "empresa" in label_lower:
                        result.employer = value

        if details:
            result.details = details

        # Fallback: body text scan
        if not result.affiliation_status:
            for line in body_text.split("\n"):
                stripped = line.strip()
                lower = stripped.lower()
                if ("afili" in lower or "estado" in lower) and ":" in stripped:
                    result.affiliation_status = stripped.split(":", 1)[1].strip()
                elif (
                    ("empleador" in lower or "empresa" in lower)
                    and ":" in stripped
                    and not result.employer
                ):
                    result.employer = stripped.split(":", 1)[1].strip()

        return result
