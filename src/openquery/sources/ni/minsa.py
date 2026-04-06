"""Nicaragua MINSA health registry source.

Queries MINSA (Ministerio de Salud) for health establishment
permits and registration data by establishment name.

URL: https://www.minsa.gob.ni/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ni.minsa import NiMinsaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

MINSA_URL = "https://www.minsa.gob.ni/"


@register
class NiMinsaSource(BaseSource):
    """Query Nicaragua MINSA for health establishment permit data."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ni.minsa",
            display_name="MINSA — Registro Establecimientos Salud Nicaragua",
            description=(
                "Nicaragua MINSA health ministry: establishment permits "
                "and health registry status by establishment name"
            ),
            country="NI",
            url=MINSA_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query MINSA for health establishment data."""
        search_term = input.extra.get("establishment_name", "") or input.document_number
        if not search_term:
            raise SourceError("ni.minsa", "establishment_name is required")
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> NiMinsaResult:
        """Full flow: launch browser, fill form, parse results."""
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("ni.minsa", "establishment_name", search_term)

        with browser.page(MINSA_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[id*="establecimiento"], input[name*="establecimiento"], '
                    'input[id*="nombre"], input[name*="nombre"], '
                    'input[id*="search"], input[name*="search"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("ni.minsa", "Could not find search input field")

                search_input.fill(search_term)
                logger.info("Filled search term: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    '#btnBuscar, input[name="btnBuscar"], '
                    'button:has-text("Buscar"), button:has-text("Consultar")'
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
                raise SourceError("ni.minsa", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> NiMinsaResult:
        """Parse health establishment data from the page DOM."""
        body_text = page.inner_text("body")
        result = NiMinsaResult(search_term=search_term)
        details: dict[str, str] = {}

        field_map = {
            "establishment name": "establishment_name",
            "nombre del establecimiento": "establishment_name",
            "nombre de establecimiento": "establishment_name",
            "nombre": "establishment_name",
            "permit status": "permit_status",
            "estado del permiso": "permit_status",
            "estado de permiso": "permit_status",
            "estado": "permit_status",
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
            "MINSA result — establishment=%s, permit_status=%s",
            result.establishment_name,
            result.permit_status,
        )
        return result
