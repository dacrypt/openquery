"""AJAM source — Bolivia mining concessions lookup.

Queries Bolivia's AJAM (Autoridad Jurisdiccional Administrativa Minera)
for mining rights and concession status by name or code.

Source: https://www.ajam.gob.bo/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.bo.ajam import AjamResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

AJAM_URL = "https://www.ajam.gob.bo/"


@register
class AjamSource(BaseSource):
    """Query Bolivia AJAM mining concessions by name or code."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="bo.ajam",
            display_name="AJAM — Concesiones Mineras",
            description=(
                "Bolivia AJAM mining concessions: mining rights and holder status by concession name or code"  # noqa: E501
            ),
            country="BO",
            url=AJAM_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (
            input.extra.get("concession_name", "")
            or input.extra.get("code", "")
            or input.document_number.strip()
        )
        if not search_term:
            raise SourceError("bo.ajam", "Concession name or code is required")
        return self._query(search_term=search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> AjamResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("bo.ajam", "search_term", search_term)

        with browser.page(AJAM_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "page_loaded")

                search_input = page.query_selector(
                    'input[name*="concesion"], input[name*="search"], '
                    'input[id*="concesion"], input[id*="search"], '
                    'input[placeholder*="concesión"], input[placeholder*="nombre"], '
                    'input[type="search"], input[type="text"]'
                )
                if not search_input:
                    raise SourceError("bo.ajam", "Could not find search input field")

                search_input.fill(search_term)
                logger.info("Querying AJAM for: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit_btn = page.query_selector(
                    'input[type="submit"], button[type="submit"], '
                    'button:has-text("Consultar"), button:has-text("Buscar"), '
                    'input[value*="Consultar"], input[value*="Buscar"]'
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
                raise SourceError("bo.ajam", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> AjamResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        concession_name = ""
        holder = ""
        status = ""

        field_map = {
            "concesión": "concession_name",
            "concesion": "concession_name",
            "nombre": "concession_name",
            "titular": "holder",
            "titulares": "holder",
            "propietario": "holder",
            "estado": "status",
            "estatus": "status",
            "vigencia": "status",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_map.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value:
                        if field == "concession_name" and not concession_name:
                            concession_name = value
                        elif field == "holder" and not holder:
                            holder = value
                        elif field == "status" and not status:
                            status = value
                    break

        return AjamResult(
            queried_at=datetime.now(),
            search_term=search_term,
            concession_name=concession_name,
            holder=holder,
            status=status,
            details=body_text.strip()[:500],
        )
