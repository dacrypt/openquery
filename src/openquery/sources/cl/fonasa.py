"""FONASA source — Chile health affiliation lookup.

Queries Chile's FONASA for health affiliation status and tier by RUT.

Flow:
1. Navigate to the FONASA portal
2. Enter RUT
3. Submit and parse affiliation status and tier (A/B/C/D)

Source: https://nuevo.fonasa.gob.cl/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.cl.fonasa import FonasaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

FONASA_URL = "https://nuevo.fonasa.gob.cl/"


@register
class FonasaSource(BaseSource):
    """Query Chile's FONASA health affiliation by RUT."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="cl.fonasa",
            display_name="FONASA — Fondo Nacional de Salud",
            description="Chile health affiliation status and tier (A/B/C/D) by RUT",
            country="CL",
            url=FONASA_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        rut = input.extra.get("rut", "").strip() or input.document_number
        if not rut:
            raise SourceError("cl.fonasa", "Must provide extra['rut'] or document_number")
        return self._query(rut=rut, audit=input.audit)

    def _query(self, rut: str, audit: bool = False) -> FonasaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("cl.fonasa", "rut", rut)

        with browser.page(FONASA_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                rut_input = page.query_selector(
                    'input[id*="rut"], input[name*="rut"], '
                    'input[id*="run"], input[name*="run"], '
                    'input[placeholder*="RUT" i], input[placeholder*="RUN" i], '
                    'input[type="text"]'
                )
                if rut_input:
                    rut_input.fill(rut)
                    logger.info("Filled RUT: %s", rut)
                else:
                    raise SourceError("cl.fonasa", "RUT input field not found")

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button:has-text("Buscar"), button:has-text("Consultar")'
                )
                if submit:
                    submit.click()
                else:
                    page.keyboard.press("Enter")

                page.wait_for_timeout(4000)
                page.wait_for_selector("body", timeout=15000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, rut)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("cl.fonasa", f"Query failed: {e}") from e

    def _parse_result(self, page, rut: str) -> FonasaResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = FonasaResult(queried_at=datetime.now(), rut=rut)
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
                    if "estado" in label_lower or "afili" in label_lower:
                        result.affiliation_status = value
                    elif "tramo" in label_lower or "grupo" in label_lower:
                        result.tier = value

        if details:
            result.details = details

        # Fallback: body text scan
        if not result.affiliation_status:
            for line in body_text.split("\n"):
                stripped = line.strip()
                lower = stripped.lower()
                if ("afili" in lower or "estado" in lower) and ":" in stripped:
                    result.affiliation_status = stripped.split(":", 1)[1].strip()
                elif ("tramo" in lower or "grupo" in lower) and ":" in stripped and not result.tier:
                    result.tier = stripped.split(":", 1)[1].strip()

        return result
