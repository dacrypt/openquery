"""Puerto Rico property registry source.

Queries the Puerto Rico Registro de la Propiedad for property ownership,
liens, and encumbrances.

Flow:
1. Navigate to https://registrodelapropiedad.pr.gov/
2. Wait for search form to load
3. Fill property number or owner name
4. Submit and parse results
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pr.registro_propiedad import RegistroPropiedadResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

REGISTRO_PROPIEDAD_URL = "https://registrodelapropiedad.pr.gov/"


@register
class RegistroPropiedadSource(BaseSource):
    """Query Puerto Rico property registry for ownership and encumbrance data."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pr.registro_propiedad",
            display_name="Registro de la Propiedad — Puerto Rico",
            description=(
                "Puerto Rico property registry: ownership, liens, encumbrances, and property value"
            ),
            country="PR",
            url=REGISTRO_PROPIEDAD_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query property registry for property data."""
        search_value = (
            input.extra.get("property_number", "")
            or input.extra.get("owner_name", "")
            or input.document_number
        )
        if not search_value:
            raise SourceError("pr.registro_propiedad", "property_number or owner_name is required")
        return self._query(search_value.strip(), audit=input.audit)

    def _query(self, search_value: str, audit: bool = False) -> RegistroPropiedadResult:
        """Full flow: launch browser, fill form, parse results."""
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("pr.registro_propiedad", "search_value", search_value)

        with browser.page(REGISTRO_PROPIEDAD_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[id*="property"], input[name*="property"], '
                    'input[id*="propiedad"], input[name*="propiedad"], '
                    'input[id*="owner"], input[name*="owner"], '
                    'input[id*="search"], input[name*="search"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("pr.registro_propiedad", "Could not find search input field")

                search_input.fill(search_value)
                logger.info("Filled search value: %s", search_value)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button:has-text("Search"), button:has-text("Buscar"), '
                    'button:has-text("Consultar")'
                )
                if submit:
                    submit.click()
                else:
                    search_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_value)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("pr.registro_propiedad", f"Query failed: {e}") from e

    def _parse_result(self, page, search_value: str) -> RegistroPropiedadResult:
        """Parse property data from the page DOM."""
        body_text = page.inner_text("body")
        result = RegistroPropiedadResult(search_value=search_value)
        details: dict[str, str] = {}

        field_map = {
            "property number": "property_number",
            "número de propiedad": "property_number",
            "numero de propiedad": "property_number",
            "finca": "property_number",
            "owner": "owner",
            "dueño": "owner",
            "dueno": "owner",
            "titular": "owner",
            "propietario": "owner",
            "liens": "liens",
            "gravámenes": "liens",
            "gravamenes": "liens",
            "cargas": "liens",
            "property value": "property_value",
            "valor": "property_value",
            "tasación": "property_value",
            "tasacion": "property_value",
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
            "RegistroPropiedad result — property_number=%s, owner=%s",
            result.property_number,
            result.owner,
        )
        return result
