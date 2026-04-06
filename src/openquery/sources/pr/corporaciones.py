"""Department of State corporation registry source — Puerto Rico.

Queries Puerto Rico's Department of State Registro de Corporaciones y
Entidades Legales (RCP) for business entity data.

Flow:
1. Navigate to https://rcp.estado.pr.gov/en
2. Wait for search form to load
3. Fill company name or registration number
4. Submit and parse results
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pr.corporaciones import CorporacionesResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CORPORACIONES_URL = "https://rcp.estado.pr.gov/en"


@register
class CorporacionesSource(BaseSource):
    """Query Puerto Rico's Department of State corporation registry."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pr.corporaciones",
            display_name="Registro Corporaciones PR — Dept. Estado",
            description=(
                "Puerto Rico Department of State corporation registry: "
                "entity name, type, status, registration date"
            ),
            country="PR",
            url=CORPORACIONES_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query corporation registry for entity data."""
        search_term = (
            input.extra.get("company_name", "")
            or input.extra.get("registration_number", "")
            or input.document_number
        )
        if not search_term:
            raise SourceError("pr.corporaciones", "company_name or registration_number is required")
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> CorporacionesResult:
        """Full flow: launch browser, fill form, parse results."""
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("pr.corporaciones", "search_term", search_term)

        with browser.page(CORPORACIONES_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Find search input
                search_input = page.query_selector(
                    'input[id*="name"], input[name*="name"], '
                    'input[id*="entity"], input[name*="entity"], '
                    'input[id*="search"], input[name*="search"], '
                    'input[id*="corp"], input[name*="corp"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("pr.corporaciones", "Could not find search input field")

                search_input.fill(search_term)
                logger.info("Filled search term: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button:has-text("Search"), button:has-text("Buscar"), '
                    'button:has-text("Find")'
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
                raise SourceError("pr.corporaciones", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> CorporacionesResult:
        """Parse corporation data from the page DOM."""
        body_text = page.inner_text("body")
        result = CorporacionesResult(search_term=search_term)
        details: dict[str, str] = {}

        field_map = {
            "entity name": "entity_name",
            "nombre": "entity_name",
            "name": "entity_name",
            "entity type": "entity_type",
            "tipo": "entity_type",
            "type": "entity_type",
            "status": "status",
            "estado": "status",
            "registration date": "registration_date",
            "fecha": "registration_date",
            "incorporated": "registration_date",
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
            "Corporaciones result — entity=%s, type=%s, status=%s",
            result.entity_name,
            result.entity_type,
            result.status,
        )
        return result
