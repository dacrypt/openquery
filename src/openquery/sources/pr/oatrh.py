"""Puerto Rico OATRH government employee verification source.

Queries OATRH (Oficina de Administración y Transformación de los
Recursos Humanos) for government employment status by employee name.

URL: https://www.oatrh.pr.gov/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pr.oatrh import PrOatrhResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

OATRH_URL = "https://www.oatrh.pr.gov/"


@register
class PrOatrhSource(BaseSource):
    """Query Puerto Rico OATRH for government employee status."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pr.oatrh",
            display_name="OATRH — Empleados Gobierno Puerto Rico",
            description=(
                "Puerto Rico OATRH government HR office: employee agency and "
                "employment status by employee name"
            ),
            country="PR",
            url=OATRH_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query OATRH for government employee data."""
        search_term = input.extra.get("employee_name", "") or input.document_number
        if not search_term:
            raise SourceError("pr.oatrh", "employee_name is required")
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> PrOatrhResult:
        """Full flow: launch browser, fill form, parse results."""
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("pr.oatrh", "employee_name", search_term)

        with browser.page(OATRH_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[id*="empleado"], input[name*="empleado"], '
                    'input[id*="nombre"], input[name*="nombre"], '
                    'input[id*="search"], input[name*="search"], '
                    'input[type="text"], input[type="search"]'
                )
                if not search_input:
                    raise SourceError("pr.oatrh", "Could not find search input field")

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
                raise SourceError("pr.oatrh", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> PrOatrhResult:
        """Parse government employee data from the page DOM."""
        body_text = page.inner_text("body")
        result = PrOatrhResult(search_term=search_term)
        details: dict[str, str] = {}

        field_map = {
            "employee name": "employee_name",
            "nombre del empleado": "employee_name",
            "nombre": "employee_name",
            "agency": "agency",
            "agencia": "agency",
            "dependencia": "agency",
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
            "OATRH result — employee=%s, agency=%s, status=%s",
            result.employee_name,
            result.agency,
            result.status,
        )
        return result
