"""IGAC source — Colombian catastro/property registry.

Queries the IGAC (Instituto Geografico Agustin Codazzi) for property/cadastral data.

Flow:
1. Navigate to IGAC consultation page
2. Enter cadastral code
3. Parse result for owner, area, land use, valuation

Source: https://www.igac.gov.co/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.igac import IgacResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

IGAC_URL = "https://www.igac.gov.co/es/contenido/servicios/consulta-de-predios"


@register
class IgacSource(BaseSource):
    """Query Colombian catastro/property registry (IGAC)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.igac",
            display_name="IGAC — Catastro Nacional",
            description="Colombian catastro/property registry (IGAC)",
            country="CO",
            url=IGAC_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        cadastral_code = input.extra.get("cadastral_code") or input.document_number
        if not cadastral_code:
            raise SourceError("co.igac", "cadastral_code is required")
        return self._query(cadastral_code, audit=input.audit)

    def _query(self, cadastral_code: str, audit: bool = False) -> IgacResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("co.igac", "custom", cadastral_code)

        with browser.page(IGAC_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[type="text"], input[id*="catastral"], '
                    'input[id*="codigo"], input[id*="predio"]'
                )
                if not search_input:
                    raise SourceError("co.igac", "Could not find cadastral code input field")

                search_input.fill(cadastral_code)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="buscar"], button[id*="consultar"]'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    search_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, cadastral_code)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("co.igac", f"Query failed: {e}") from e

    def _parse_result(self, page, cadastral_code: str) -> IgacResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        owner = ""
        area = ""
        land_use = ""
        valuation = ""

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if not stripped:
                continue
            if ("propietario" in lower or "titular" in lower) and ":" in stripped:
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not owner:
                    owner = parts[1].strip()
            elif "area" in lower and ":" in stripped:
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not area:
                    area = parts[1].strip()
            elif ("uso" in lower or "destino" in lower) and ":" in stripped:
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not land_use:
                    land_use = parts[1].strip()
            elif ("avalu" in lower or "valor" in lower) and ":" in stripped:
                parts = stripped.split(":", 1)
                if len(parts) > 1 and not valuation:
                    valuation = parts[1].strip()

        return IgacResult(
            queried_at=datetime.now(),
            cadastral_code=cadastral_code,
            owner=owner,
            area=area,
            land_use=land_use,
            valuation=valuation,
            details={"queried": True},
        )
