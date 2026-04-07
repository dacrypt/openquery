"""Aduana source — Bolivia customs declarations.

Queries the Aduana Nacional de Bolivia for customs declaration status.

Source: https://www.aduana.gob.bo/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.bo.aduana import AduanaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

ADUANA_URL = "https://www.aduana.gob.bo/"


@register
class AduanaSource(BaseSource):
    """Query Bolivia Aduana Nacional customs declarations by declaration number."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="bo.aduana",
            display_name="Aduana Nacional — Declaraciones Aduaneras",
            description=(
                "Bolivia Aduana Nacional: customs declaration status by declaration number"
            ),
            country="BO",
            url=ADUANA_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        declaration_number = input.extra.get("declaration_number", "") or input.document_number.strip()  # noqa: E501
        if not declaration_number:
            raise SourceError("bo.aduana", "Declaration number is required")
        return self._query(declaration_number=declaration_number, audit=input.audit)

    def _query(self, declaration_number: str, audit: bool = False) -> AduanaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("bo.aduana", "declaration_number", declaration_number)

        with browser.page(ADUANA_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "page_loaded")

                search_input = page.query_selector(
                    'input[name*="declaracion"], input[id*="declaracion"], '
                    'input[name*="numero"], input[type="text"], '
                    'input[name*="dui"], input[type="search"]'
                )
                if search_input:
                    search_input.fill(declaration_number)
                    logger.info("Querying Aduana BO for declaration: %s", declaration_number)

                    submit_btn = page.query_selector(
                        'button[type="submit"], input[type="submit"], '
                        'button:has-text("Consultar"), button:has-text("Buscar")'
                    )
                    if submit_btn:
                        submit_btn.click()
                    else:
                        search_input.press("Enter")

                    page.wait_for_timeout(4000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, declaration_number)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("bo.aduana", f"Query failed: {e}") from e

    def _parse_result(self, page, declaration_number: str) -> AduanaResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        declarant_name = ""
        customs_status = ""
        declaration_date = ""
        goods_description = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if any(kw in lower for kw in ["declarante", "importador", "exportador"]) and ":" in stripped and not declarant_name:  # noqa: E501
                declarant_name = stripped.split(":", 1)[1].strip()
            elif "estado" in lower and ":" in stripped and not customs_status:
                customs_status = stripped.split(":", 1)[1].strip()
            elif any(kw in lower for kw in ["fecha", "registro"]) and ":" in stripped and not declaration_date:  # noqa: E501
                declaration_date = stripped.split(":", 1)[1].strip()
            elif any(kw in lower for kw in ["mercancía", "descripción", "producto"]) and ":" in stripped and not goods_description:  # noqa: E501
                goods_description = stripped.split(":", 1)[1].strip()

        return AduanaResult(
            queried_at=datetime.now(),
            declaration_number=declaration_number,
            declarant_name=declarant_name,
            customs_status=customs_status,
            declaration_date=declaration_date,
            goods_description=goods_description,
            details=body_text.strip()[:500],
        )
