"""Nicaragua SIBOIF banking regulator source.

Queries the SIBOIF (Superintendencia de Bancos y de Otras Instituciones
Financieras) portal for supervised entity and banking license data.

Flow:
1. Navigate to https://www.siboif.gob.ni/
2. Wait for search form to load
3. Fill entity name
4. Submit and parse results
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ni.siboif import NiSiboifResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SIBOIF_URL = "https://www.siboif.gob.ni/"


@register
class NiSiboifSource(BaseSource):
    """Query Nicaragua SIBOIF for supervised entity and banking license data."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ni.siboif",
            display_name="SIBOIF — Entidades Supervisadas Nicaragua",
            description=(
                "Nicaragua SIBOIF banking regulator: supervised entities, "
                "banking license status, and entity type"
            ),
            country="NI",
            url=SIBOIF_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query SIBOIF for supervised entity data."""
        search_term = (
            input.extra.get("entity_name", "")
            or input.document_number
        )
        if not search_term:
            raise SourceError("ni.siboif", "entity_name is required")
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> NiSiboifResult:
        """Full flow: launch browser, fill form, parse results."""
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("ni.siboif", "search_term", search_term)

        with browser.page(SIBOIF_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[id*="entity"], input[name*="entity"], '
                    'input[id*="entidad"], input[name*="entidad"], '
                    'input[id*="nombre"], input[name*="nombre"], '
                    'input[id*="search"], input[name*="search"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("ni.siboif", "Could not find search input field")

                search_input.fill(search_term)
                logger.info("Filled search term: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    '#btnBuscar, input[name="btnBuscar"], '
                    '#btnConsultar, input[name="btnConsultar"], '
                    'button[type="submit"], input[type="submit"]'
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
                raise SourceError("ni.siboif", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> NiSiboifResult:
        """Parse supervised entity data from the page DOM."""
        body_text = page.inner_text("body")
        result = NiSiboifResult(search_term=search_term)
        details: dict[str, str] = {}

        field_map = {
            "entity name": "entity_name",
            "nombre de la entidad": "entity_name",
            "nombre": "entity_name",
            "license status": "license_status",
            "estado de licencia": "license_status",
            "estado": "license_status",
            "entity type": "entity_type",
            "tipo de entidad": "entity_type",
            "tipo": "entity_type",
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
            "SIBOIF result — entity=%s, license_status=%s, entity_type=%s",
            result.entity_name, result.license_status, result.entity_type,
        )
        return result
