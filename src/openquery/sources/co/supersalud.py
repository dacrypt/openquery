"""Colombia Supersalud source — health entities lookup.

Queries Supersalud portal for EPS, IPS, and other health entities by name.
Browser-based, public access.

Source: https://www.supersalud.gov.co/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.supersalud import SupersaludResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SUPERSALUD_URL = "https://www.supersalud.gov.co/es-co/entidades-vigiladas"


@register
class SupersaludSource(BaseSource):
    """Query Supersalud for supervised health entities (EPS/IPS)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.supersalud",
            display_name="Supersalud — Entidades Vigiladas (EPS/IPS)",
            description="Colombia Supersalud health entities lookup: EPS, IPS, and other supervised entities",  # noqa: E501
            country="CO",
            url=SUPERSALUD_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("search_term", "") or input.document_number
        if not search_term:
            raise SourceError("co.supersalud", "Entity name is required")
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> SupersaludResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("co.supersalud", "search_term", search_term)

        with browser.page(SUPERSALUD_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[placeholder*="entidad" i], input[placeholder*="buscar" i], '
                    'input[name*="search" i], input[id*="search" i], '
                    'input[type="search"], input[type="text"]'
                )
                if not search_input:
                    raise SourceError("co.supersalud", "Could not find search input field")

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
                raise SourceError("co.supersalud", f"Query failed: {e}") from e

    def _parse_result(self, page: object, search_term: str) -> SupersaludResult:
        from datetime import datetime

        body_text = page.inner_text("body")  # type: ignore[union-attr]
        body_lower = body_text.lower()
        entity_name = ""
        entity_type = ""
        status = ""
        details: dict[str, str] = {}

        not_found_phrases = ("no se encontr", "sin resultados", "no registra")
        if any(phrase in body_lower for phrase in not_found_phrases):
            return SupersaludResult(
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

                if any(k in lower for k in ("entidad", "razón", "nombre")):
                    if not entity_name and val_clean:
                        entity_name = val_clean

                if any(k in lower for k in ("tipo", "clase", "eps", "ips")):
                    if not entity_type and val_clean:
                        entity_type = val_clean

                if any(k in lower for k in ("estado", "situación", "habilitación", "vigencia")):
                    if not status and val_clean:
                        status = val_clean

        return SupersaludResult(
            queried_at=datetime.now(),
            search_term=search_term,
            entity_name=entity_name,
            entity_type=entity_type,
            status=status,
            details=details,
        )
