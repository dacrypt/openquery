"""Servel source — Chile electoral service lookup.

Queries Chile's Servel for electoral information and voting location by RUT.

Flow:
1. Navigate to the Servel portal
2. Enter RUT
3. Submit and parse electoral info and voting location

Source: https://www.servel.cl/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.cl.servel import ServelResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SERVEL_URL = "https://www.servel.cl/"


@register
class ServelSource(BaseSource):
    """Query Chile's Servel electoral service by RUT."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="cl.servel",
            display_name="Servel — Servicio Electoral de Chile",
            description="Chile electoral info: voting location and electoral status by RUT",
            country="CL",
            url=SERVEL_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CUSTOM:
            raise SourceError("cl.servel", f"Unsupported input type: {input.document_type}")

        rut = input.extra.get("rut", "").strip()
        if not rut:
            raise SourceError("cl.servel", "Must provide extra['rut'] (RUT)")

        return self._query(rut=rut, audit=input.audit)

    def _query(self, rut: str, audit: bool = False) -> ServelResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("cl.servel", "rut", rut)

        with browser.page(SERVEL_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                rut_input = page.query_selector(
                    'input[id*="rut"], input[name*="rut"], '
                    'input[placeholder*="RUT" i], input[type="text"]:first-of-type'
                )
                if rut_input:
                    rut_input.fill(rut)
                    logger.info("Filled RUT: %s", rut)
                else:
                    raise SourceError("cl.servel", "RUT input field not found")

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
                raise SourceError("cl.servel", f"Query failed: {e}") from e

    def _parse_result(self, page, rut: str) -> ServelResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = ServelResult(queried_at=datetime.now(), rut=rut)
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
                    if "nombre" in label_lower:
                        result.nombre = value
                    elif "local" in label_lower or "mesa" in label_lower or "circunscripci" in label_lower:  # noqa: E501
                        result.voting_location = value

        if details:
            result.details = details

        # Fallback: body text scan
        if not result.nombre:
            for line in body_text.split("\n"):
                stripped = line.strip()
                lower = stripped.lower()
                if "nombre" in lower and ":" in stripped:
                    result.nombre = stripped.split(":", 1)[1].strip()
                elif (
                    ("local" in lower or "mesa" in lower or "circunscripci" in lower)
                    and ":" in stripped
                    and not result.voting_location
                ):
                    result.voting_location = stripped.split(":", 1)[1].strip()

        return result
