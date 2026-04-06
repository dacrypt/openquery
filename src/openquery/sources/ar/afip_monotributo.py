"""AFIP Monotributo source — Argentina monotributo status lookup.

Queries Argentina's AFIP for monotributo category and status by CUIT.

Flow:
1. Navigate to the AFIP portal
2. Enter CUIT
3. Submit and parse monotributo category and status

Source: https://www.afip.gob.ar/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ar.afip_monotributo import AfipMonotributoResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

AFIP_MONOTRIBUTO_URL = "https://www.afip.gob.ar/"


@register
class AfipMonotributoSource(BaseSource):
    """Query Argentina's AFIP for monotributo status by CUIT."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ar.afip_monotributo",
            display_name="AFIP — Monotributo",
            description="Argentina AFIP monotributo: category and status by CUIT",
            country="AR",
            url=AFIP_MONOTRIBUTO_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CUSTOM:
            raise SourceError("ar.afip_monotributo", f"Unsupported input type: {input.document_type}")  # noqa: E501

        cuit = input.extra.get("cuit", "").strip()
        if not cuit:
            raise SourceError("ar.afip_monotributo", "Must provide extra['cuit'] (CUIT)")

        return self._query(cuit=cuit, audit=input.audit)

    def _query(self, cuit: str, audit: bool = False) -> AfipMonotributoResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("ar.afip_monotributo", "cuit", cuit)

        with browser.page(AFIP_MONOTRIBUTO_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                cuit_input = page.query_selector(
                    'input[id*="cuit"], input[name*="cuit"], '
                    'input[placeholder*="CUIT" i], input[type="text"]:first-of-type'
                )
                if cuit_input:
                    cuit_input.fill(cuit)
                    logger.info("Filled CUIT: %s", cuit)
                else:
                    raise SourceError("ar.afip_monotributo", "CUIT input field not found")

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

                result = self._parse_result(page, cuit)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("ar.afip_monotributo", f"Query failed: {e}") from e

    def _parse_result(self, page, cuit: str) -> AfipMonotributoResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = AfipMonotributoResult(queried_at=datetime.now(), cuit=cuit)
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
                    if "nombre" in label_lower or "denominaci" in label_lower or "raz" in label_lower:  # noqa: E501
                        result.taxpayer_name = value
                    elif "categor" in label_lower:
                        result.category = value
                    elif "estado" in label_lower or "condici" in label_lower or "estatus" in label_lower:  # noqa: E501
                        result.status = value

        if details:
            result.details = details

        # Fallback: body text scan
        if not result.taxpayer_name:
            for line in body_text.split("\n"):
                stripped = line.strip()
                lower = stripped.lower()
                if ("nombre" in lower or "denominaci" in lower) and ":" in stripped:
                    result.taxpayer_name = stripped.split(":", 1)[1].strip()
                elif "categor" in lower and ":" in stripped and not result.category:
                    result.category = stripped.split(":", 1)[1].strip()
                elif ("estado" in lower or "condici" in lower) and ":" in stripped and not result.status:  # noqa: E501
                    result.status = stripped.split(":", 1)[1].strip()

        return result
