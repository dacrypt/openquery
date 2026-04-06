"""ARCSA source — Ecuador health product registry lookup.

Queries Ecuador's ARCSA for sanitary registrations by product name.

Flow:
1. Navigate to the ARCSA portal
2. Enter product name
3. Submit and parse registration number and status

Source: https://www.controlsanitario.gob.ec/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ec.arcsa import ArcsaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

ARCSA_URL = "https://www.controlsanitario.gob.ec/"


@register
class ArcsaSource(BaseSource):
    """Query Ecuador's ARCSA health product registry by product name."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ec.arcsa",
            display_name="ARCSA — Agencia Nacional de Regulación, Control y Vigilancia Sanitaria",
            description="Ecuador health product registry: sanitary registration number and status by product name",  # noqa: E501
            country="EC",
            url=ARCSA_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CUSTOM:
            raise SourceError("ec.arcsa", f"Unsupported input type: {input.document_type}")

        search_term = input.extra.get("product", "").strip()
        if not search_term:
            raise SourceError("ec.arcsa", "Must provide extra['product'] (product name)")

        return self._query(search_term=search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> ArcsaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("ec.arcsa", "producto", search_term)

        with browser.page(ARCSA_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[id*="producto"], input[name*="producto"], '
                    'input[placeholder*="producto" i], input[type="search"], '
                    'input[type="text"]'
                )
                if search_input:
                    search_input.fill(search_term)
                    logger.info("Filled product name: %s", search_term)

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

                result = self._parse_result(page, search_term)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("ec.arcsa", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> ArcsaResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = ArcsaResult(queried_at=datetime.now(), search_term=search_term)
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
                    if "producto" in label_lower or "nombre" in label_lower or "descripci" in label_lower:  # noqa: E501
                        result.product_name = value
                    elif "registro" in label_lower or "n\u00famero" in label_lower or "numero" in label_lower:  # noqa: E501
                        result.registration_number = value
                    elif "estado" in label_lower or "vigencia" in label_lower or "condici" in label_lower:  # noqa: E501
                        result.status = value

        if details:
            result.details = details

        # Fallback: body text scan
        if not result.product_name:
            for line in body_text.split("\n"):
                stripped = line.strip()
                lower = stripped.lower()
                if ("producto" in lower or "nombre" in lower) and ":" in stripped:
                    result.product_name = stripped.split(":", 1)[1].strip()
                elif "registro" in lower and ":" in stripped and not result.registration_number:
                    result.registration_number = stripped.split(":", 1)[1].strip()
                elif ("estado" in lower or "vigencia" in lower) and ":" in stripped and not result.status:  # noqa: E501
                    result.status = stripped.split(":", 1)[1].strip()

        return result
