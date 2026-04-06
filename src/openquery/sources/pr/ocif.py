"""Puerto Rico OCIF banking supervisor source.

Queries OCIF (Oficina del Comisionado de Instituciones Financieras) for
supervised financial institution data by entity name.

URL: https://www.ocif.gobierno.pr/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pr.ocif import PrOcifResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

OCIF_URL = "https://www.ocif.gobierno.pr/"


@register
class PrOcifSource(BaseSource):
    """Query Puerto Rico OCIF for supervised financial institution data."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pr.ocif",
            display_name="OCIF — Instituciones Financieras Supervisadas Puerto Rico",
            description=(
                "Puerto Rico OCIF banking supervisor: supervised financial institutions, "
                "entity type and status by entity name"
            ),
            country="PR",
            url=OCIF_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query OCIF for supervised institution data."""
        search_term = input.extra.get("entity_name", "") or input.document_number
        if not search_term:
            raise SourceError("pr.ocif", "entity_name is required")
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> PrOcifResult:
        """Full flow: launch browser, fill form, parse results."""
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("pr.ocif", "entity_name", search_term)

        with browser.page(OCIF_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[id*="entidad"], input[name*="entidad"], '
                    'input[id*="institucion"], input[name*="institucion"], '
                    'input[id*="nombre"], input[name*="nombre"], '
                    'input[id*="search"], input[name*="search"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("pr.ocif", "Could not find search input field")

                search_input.fill(search_term)
                logger.info("Filled search term: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button:has-text("Buscar"), button:has-text("Search")'
                )
                if submit:
                    submit.click()
                else:
                    search_input.press("Enter")

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
                raise SourceError("pr.ocif", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> PrOcifResult:
        """Parse supervised institution data from the page DOM."""
        body_text = page.inner_text("body")
        result = PrOcifResult(search_term=search_term)
        details: dict[str, str] = {}

        field_map = {
            "entity name": "entity_name",
            "nombre de la entidad": "entity_name",
            "nombre de entidad": "entity_name",
            "nombre": "entity_name",
            "entity type": "entity_type",
            "tipo de entidad": "entity_type",
            "tipo de institución": "entity_type",
            "tipo": "entity_type",
            "status": "status",
            "estado": "status",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            lower = stripped.lower()
            for label, attr in field_map.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value:
                        setattr(result, attr, value)
                    break
            if ":" in stripped:
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip()
                if key and val:
                    details[key] = val

        result.details = details
        logger.info(
            "OCIF result — entity=%s, type=%s, status=%s",
            result.entity_name,
            result.entity_type,
            result.status,
        )
        return result
