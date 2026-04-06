"""SCVS source — Ecuador Superintendencia de Compañías company registry.

Queries Ecuador's SCVS mobile portal for company information by RUC or name.

Flow:
1. Navigate to the SCVS portal
2. Enter RUC or company name
3. Submit and parse result

Source: https://appscvsmovil.supercias.gob.ec/portalInformacion/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ec.scvs import ScvsResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SCVS_URL = "https://appscvsmovil.supercias.gob.ec/portalInformacion/"


@register
class ScvsSource(BaseSource):
    """Query Ecuador company registry from SCVS portal."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ec.scvs",
            display_name="SCVS — Superintendencia de Compañías",
            description="Ecuador company registry: legal status, representative, and details",
            country="EC",
            url=SCVS_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CUSTOM:
            raise SourceError("ec.scvs", f"Unsupported input type: {input.document_type}")

        ruc = input.extra.get("ruc", "").strip()
        name = input.extra.get("name", "").strip()

        if not ruc and not name:
            raise SourceError("ec.scvs", "Must provide extra['ruc'] or extra['name']")

        return self._query(ruc=ruc, name=name, audit=input.audit)

    def _query(self, ruc: str = "", name: str = "", audit: bool = False) -> ScvsResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None
        search_term = ruc or name

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("ec.scvs", "ruc" if ruc else "nombre", search_term)

        with browser.page(SCVS_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[id*="ruc"], input[name*="ruc"], '
                    'input[id*="nombre"], input[name*="nombre"], '
                    'input[id*="busqueda"], input[type="text"]'
                )
                if search_input:
                    search_input.fill(search_term)
                    logger.info("Filled search term: %s", search_term)

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

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_term)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("ec.scvs", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> ScvsResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = ScvsResult(queried_at=datetime.now(), search_term=search_term)
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
                    if ("raz" in label_lower and "social" in label_lower) or "nombre" in label_lower:
                        result.company_name = value
                    elif "ruc" in label_lower:
                        result.ruc = value
                    elif "estado" in label_lower:
                        result.status = value
                    elif "representante" in label_lower:
                        result.legal_representative = value

        if details:
            result.details = details

        # Fallback: body text scan
        if not result.company_name:
            for line in body_text.split("\n"):
                stripped = line.strip()
                lower = stripped.lower()
                if ("raz" in lower and "social" in lower) and ":" in stripped:
                    result.company_name = stripped.split(":", 1)[1].strip()
                elif "ruc" in lower and ":" in stripped and not result.ruc:
                    result.ruc = stripped.split(":", 1)[1].strip()
                elif "estado" in lower and ":" in stripped and not result.status:
                    result.status = stripped.split(":", 1)[1].strip()
                elif "representante" in lower and ":" in stripped and not result.legal_representative:
                    result.legal_representative = stripped.split(":", 1)[1].strip()

        return result
