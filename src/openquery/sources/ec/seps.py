"""SEPS source — Ecuador Superintendencia de Economía Popular y Solidaria.

Queries Ecuador's SEPS for cooperative and organization lookup
by RUC or organization name.

Flow:
1. Navigate to the SEPS consultation page
2. Enter RUC or organization name
3. Submit and parse result

Source: https://www.seps.gob.ec/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ec.seps import SepsResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SEPS_URL = "https://www.seps.gob.ec/"


@register
class SepsSource(BaseSource):
    """Query Ecuador organization registry from SEPS."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ec.seps",
            display_name="SEPS — Superintendencia de Economía Popular y Solidaria",
            description="Ecuador cooperative and organization lookup from SEPS",
            country="EC",
            url=SEPS_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CUSTOM:
            raise SourceError("ec.seps", f"Unsupported input type: {input.document_type}")

        ruc = input.extra.get("ruc", "").strip()
        name = input.extra.get("name", "").strip()

        if not ruc and not name:
            raise SourceError("ec.seps", "Must provide extra['ruc'] or extra['name']")

        return self._query(ruc=ruc, name=name, audit=input.audit)

    def _query(self, ruc: str = "", name: str = "", audit: bool = False) -> SepsResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None
        search_term = ruc or name

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("ec.seps", "ruc" if ruc else "nombre", search_term)

        with browser.page(SEPS_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill search input
                if ruc:
                    search_input = page.query_selector(
                        'input[id*="ruc"], input[name*="ruc"], '
                        'input[id*="numero"], input[type="text"]'
                    )
                else:
                    search_input = page.query_selector(
                        'input[id*="nombre"], input[id*="organizacion"], '
                        'input[name*="nombre"], input[type="text"]'
                    )

                if not search_input:
                    raise SourceError("ec.seps", "Could not find search input field")

                search_input.fill(search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="consultar"], button[id*="buscar"], '
                    'button:has-text("Consultar"), button:has-text("Buscar")'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    search_input.press("Enter")

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
                raise SourceError("ec.seps", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> SepsResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        organization_name = ""
        ruc = ""
        status = ""
        organization_type = ""
        details: dict[str, str] = {}

        for line in body_text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            lower = stripped.lower()
            if (
                "raz" in lower and "social" in lower
                or "nombre" in lower and "organizaci" in lower
            ) and ":" in stripped:
                organization_name = stripped.split(":", 1)[1].strip()
            elif "ruc" in lower and ":" in stripped:
                ruc = stripped.split(":", 1)[1].strip()
            elif "estado" in lower and ":" in stripped:
                status = stripped.split(":", 1)[1].strip()
            elif ("tipo" in lower or "clase" in lower or "sector" in lower) and ":" in stripped:
                organization_type = stripped.split(":", 1)[1].strip()
            elif ":" in stripped:
                key, _, val = stripped.partition(":")
                if key.strip() and val.strip():
                    details[key.strip()] = val.strip()

        return SepsResult(
            queried_at=datetime.now(),
            search_term=search_term,
            organization_name=organization_name,
            ruc=ruc,
            status=status,
            organization_type=organization_type,
            details=details,
        )
