"""Bolivia DDRR source — Derechos Reales property registry.

Queries Bolivia's property registry for ownership, liens, and encumbrances.

Source: https://magistratura.organojudicial.gob.bo/consultaddrr/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.bo.ddrr import DdrrResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

DDRR_URL = "https://magistratura.organojudicial.gob.bo/consultaddrr/"


@register
class DdrrSource(BaseSource):
    """Query Bolivia's Derechos Reales property registry by folio or document number."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="bo.ddrr",
            display_name="DDRR — Derechos Reales",
            description=(
                "Bolivia property registry: ownership, liens, encumbrances"
                " (Derechos Reales — Órgano Judicial)"
            ),
            country="BO",
            url=DDRR_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_value = (
            input.extra.get("folio", "")
            or input.extra.get("document_number", "")
            or input.document_number
        )
        if not search_value:
            raise SourceError("bo.ddrr", "folio or document_number is required")
        return self._query(search_value.strip(), audit=input.audit)

    def _query(self, search_value: str, audit: bool = False) -> DdrrResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("bo.ddrr", "search_value", search_value)

        with browser.page(DDRR_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[name*="folio"], input[name*="Folio"], '
                    'input[id*="folio"], input[placeholder*="folio"], '
                    'input[placeholder*="documento"], input[type="text"]'
                )
                if not search_input:
                    raise SourceError("bo.ddrr", "Could not find search input field")

                search_input.fill(search_value)
                logger.info("Filled search value: %s", search_value)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'input[type="submit"], button[type="submit"], '
                    'button:has-text("Consultar"), button:has-text("Buscar"), '
                    'button:has-text("Verificar")'
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
                raise SourceError("bo.ddrr", f"Query failed: {e}") from e

    def _parse_result(self, page, search_value: str) -> DdrrResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = DdrrResult(queried_at=datetime.now(), search_value=search_value)

        liens: list[str] = []
        details: dict[str, str] = {}

        field_map = {
            "folio": "folio",
            "propietario": "owner",
            "titular": "owner",
            "dueño": "owner",
            "tipo de bien": "property_type",
            "tipo bien": "property_type",
            "tipo": "property_type",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()

            # Liens/encumbrances
            if any(kw in lower for kw in ("gravamen", "hipoteca", "embargo", "carga")):
                if stripped:
                    liens.append(stripped)
                continue

            for label, field in field_map.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value:
                        setattr(result, field, value)
                    break
            else:
                # Collect remaining key:value pairs as details
                if ":" in stripped and len(stripped) < 200:
                    parts = stripped.split(":", 1)
                    key = parts[0].strip()
                    val = parts[1].strip()
                    if key and val and len(key) < 60:
                        details[key] = val

        result.liens = liens
        result.details = details
        return result
