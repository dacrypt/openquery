"""Panama MINSA source — health registry lookup.

Queries Panama MINSA portal for health establishment permits and
registrations by establishment name.
Browser-based, public access.

Source: https://www.minsa.gob.pa/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pa.minsa import MinsaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

MINSA_URL = "https://www.minsa.gob.pa/establecimientos"


@register
class MinsaSource(BaseSource):
    """Query Panama MINSA for health establishment permits and registry."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pa.minsa",
            display_name="MINSA — Registro de Establecimientos de Salud",
            description="Panama MINSA health establishment permit and registry lookup by name",
            country="PA",
            url=MINSA_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("search_term", "") or input.document_number
        if not search_term:
            raise SourceError("pa.minsa", "Establishment name is required")
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> MinsaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("pa.minsa", "search_term", search_term)

        with browser.page(MINSA_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[placeholder*="establecimiento" i], input[placeholder*="buscar" i], '
                    'input[name*="establecimiento" i], input[id*="establecimiento" i], '
                    'input[type="search"], input[type="text"]'
                )
                if not search_input:
                    raise SourceError("pa.minsa", "Could not find search input field")

                search_input.fill(search_term)
                logger.info("Filled search term: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="buscar" i], button[id*="consultar" i]'
                )
                if submit:
                    submit.click()
                else:
                    search_input.press("Enter")

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(3000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_term)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("pa.minsa", f"Query failed: {e}") from e

    def _parse_result(self, page: object, search_term: str) -> MinsaResult:
        from datetime import datetime

        body_text = page.inner_text("body")  # type: ignore[union-attr]
        body_lower = body_text.lower()
        establishment_name = ""
        permit_status = ""
        details: dict[str, str] = {}

        not_found_phrases = ("no se encontr", "sin resultados", "no registra", "no existe")
        if any(phrase in body_lower for phrase in not_found_phrases):
            return MinsaResult(
                queried_at=datetime.now(),
                search_term=search_term,
            )

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if not stripped:
                continue

            if ":" in stripped:
                key, _, val = stripped.partition(":")
                key_clean = key.strip()
                val_clean = val.strip()
                if val_clean:
                    details[key_clean] = val_clean

                if any(k in lower for k in ("establecimiento", "nombre", "razón")):
                    if not establishment_name and val_clean:
                        establishment_name = val_clean

                if any(k in lower for k in ("permiso", "habilitación", "estado", "situación")):
                    if not permit_status and val_clean:
                        permit_status = val_clean

        return MinsaResult(
            queried_at=datetime.now(),
            search_term=search_term,
            establishment_name=establishment_name,
            permit_status=permit_status,
            details=details,
        )
