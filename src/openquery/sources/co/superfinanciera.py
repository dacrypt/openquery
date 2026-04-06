"""Colombia Superfinanciera source — supervised entities lookup.

Queries Superfinanciera portal for supervised banks, insurance companies,
and other financial entities by name.
Browser-based, public access.

Source: https://www.superfinanciera.gov.co/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.superfinanciera import SuperfinancieraResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SUPERFINANCIERA_URL = "https://www.superfinanciera.gov.co/publicaciones/10038768/entidades-vigiladas/"


@register
class SuperfinancieraSource(BaseSource):
    """Query Superfinanciera for supervised financial entities."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.superfinanciera",
            display_name="Superfinanciera — Entidades Vigiladas",
            description="Colombia Superfinanciera supervised entities lookup (banks, insurance, financial)",  # noqa: E501
            country="CO",
            url=SUPERFINANCIERA_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("search_term", "") or input.document_number
        if not search_term:
            raise SourceError("co.superfinanciera", "Entity name is required")
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> SuperfinancieraResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("co.superfinanciera", "search_term", search_term)

        with browser.page(SUPERFINANCIERA_URL) as page:
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
                    raise SourceError(
                        "co.superfinanciera", "Could not find search input field"
                    )

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
                raise SourceError("co.superfinanciera", f"Query failed: {e}") from e

    def _parse_result(self, page: object, search_term: str) -> SuperfinancieraResult:
        from datetime import datetime

        body_text = page.inner_text("body")  # type: ignore[union-attr]
        body_lower = body_text.lower()
        entity_name = ""
        entity_type = ""
        supervision_status = ""
        details: dict[str, str] = {}

        not_found_phrases = ("no se encontr", "sin resultados", "no registra")
        if any(phrase in body_lower for phrase in not_found_phrases):
            return SuperfinancieraResult(
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

                if any(k in lower for k in ("tipo", "clase", "sector")):
                    if not entity_type and val_clean:
                        entity_type = val_clean

                if any(k in lower for k in ("estado", "situación", "vigencia", "autorización")):
                    if not supervision_status and val_clean:
                        supervision_status = val_clean

        return SuperfinancieraResult(
            queried_at=datetime.now(),
            search_term=search_term,
            entity_name=entity_name,
            entity_type=entity_type,
            supervision_status=supervision_status,
            details=details,
        )
