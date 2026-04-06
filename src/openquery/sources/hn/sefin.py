"""Honduras SEFIN government budget/transparency source.

Queries SEFIN (Secretaría de Finanzas) for government budget and
transparency data by entity name.

URL: https://www.sefin.gob.hn/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.hn.sefin import HnSefinResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SEFIN_URL = "https://www.sefin.gob.hn/"


@register
class HnSefinSource(BaseSource):
    """Query Honduras SEFIN for government budget and transparency data."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="hn.sefin",
            display_name="SEFIN — Transparencia Presupuestaria Honduras",
            description=(
                "Honduras SEFIN finance ministry: government budget data "
                "and budget transparency by entity name"
            ),
            country="HN",
            url=SEFIN_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query SEFIN for budget transparency data."""
        search_term = input.extra.get("entity_name", "") or input.document_number
        if not search_term:
            raise SourceError("hn.sefin", "entity_name is required")
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> HnSefinResult:
        """Full flow: launch browser, fill form, parse results."""
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("hn.sefin", "entity_name", search_term)

        with browser.page(SEFIN_URL) as page:
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
                    raise SourceError("hn.sefin", "Could not find search input field")

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
                raise SourceError("hn.sefin", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> HnSefinResult:
        """Parse budget transparency data from the page DOM."""
        body_text = page.inner_text("body")
        result = HnSefinResult(search_term=search_term)
        details: dict[str, str] = {}

        field_map = {
            "entity name": "entity_name",
            "nombre de la entidad": "entity_name",
            "nombre de entidad": "entity_name",
            "nombre": "entity_name",
            "budget amount": "budget_amount",
            "monto del presupuesto": "budget_amount",
            "presupuesto": "budget_amount",
            "monto": "budget_amount",
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
            "SEFIN result — entity=%s, budget=%s",
            result.entity_name,
            result.budget_amount,
        )
        return result
