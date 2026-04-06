"""Dominican Republic ONAPI source — trademark search.

Queries ONAPI for trademark registrations, owner, status, and classes.

Source: https://www.onapi.gov.do/index.php/busqueda-de-signos-nombres-y-marcas
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.do.onapi import DoOnapiResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

ONAPI_URL = "https://www.onapi.gov.do/index.php/busqueda-de-signos-nombres-y-marcas"


@register
class DoOnapiSource(BaseSource):
    """Query Dominican Republic ONAPI trademark registry."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="do.onapi",
            display_name="ONAPI — Búsqueda de Marcas",
            description=(
                "Dominican Republic trademark search: registrations, owner, status, classes (ONAPI)"
            ),
            country="DO",
            url=ONAPI_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (
            input.document_number or input.extra.get("marca", "") or input.extra.get("term", "")
        )
        if not search_term:
            raise SourceError("do.onapi", "Trademark name or search term is required")
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> DoOnapiResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("do.onapi", "marca", search_term)

        with browser.page(ONAPI_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[name*="busqueda"], input[id*="busqueda"], '
                    'input[name*="marca"], input[id*="marca"], '
                    'input[name*="search"], input[id*="search"], '
                    'input[placeholder*="marca"], input[placeholder*="signo"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("do.onapi", "Could not find search input field")

                search_input.fill(search_term)
                logger.info("Filled search term: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button:has-text("Buscar"), button:has-text("Consultar")'
                )
                if submit:
                    submit.click()
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
                raise SourceError("do.onapi", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> DoOnapiResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = DoOnapiResult(queried_at=datetime.now(), search_term=search_term)

        field_map = {
            "marca": "trademark_name",
            "signo": "trademark_name",
            "titular": "owner",
            "propietario": "owner",
            "estado": "status",
            "clase": "classes",
            "registro": "registration_date",
            "fecha": "registration_date",
        }

        lines = body_text.split("\n")
        for line in lines:
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_map.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value:
                        setattr(result, field, value)
                    break

        if body_text.strip():
            result.details = body_text.strip()[:500]

        return result
