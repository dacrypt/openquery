"""Puerto Rico DACO consumer affairs source.

Queries Puerto Rico DACO (Departamento de Asuntos del Consumidor).
Browser-based, no CAPTCHA.

URL: https://www.daco.pr.gov/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pr.daco import PrDacoResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

DACO_URL = "https://www.daco.pr.gov/"


@register
class PrDacoSource(BaseSource):
    """Query Puerto Rico DACO consumer affairs complaints and license status."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pr.daco",
            display_name="DACO — Asuntos del Consumidor (PR)",
            description="Puerto Rico DACO: company complaints count and license status by name",
            country="PR",
            url=DACO_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("company_name", "") or input.document_number
        if not search_term:
            raise SourceError("pr.daco", "Company name is required")
        return self._query(search_term.strip(), audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> PrDacoResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("pr.daco", "company_name", search_term)

        with browser.page(DACO_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    "input[name*='empresa'], input[id*='empresa'], "
                    "input[name*='company'], input[name*='buscar'], input[type='text']"
                )
                if not search_input:
                    raise SourceError("pr.daco", "Could not find search input field")

                search_input.fill(search_term)
                logger.info("Filled company name: %s", search_term)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    "button[type='submit'], input[type='submit'], button[id*='buscar']"
                )
                if submit:
                    submit.click()
                else:
                    search_input.press("Enter")

                page.wait_for_timeout(3000)
                page.wait_for_selector(
                    "table, .resultado, .result, #resultado",
                    timeout=15000,
                )

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_term)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("pr.daco", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> PrDacoResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = PrDacoResult(queried_at=datetime.now(), search_term=search_term)

        field_patterns = {
            "empresa": "company_name",
            "comercio": "company_name",
            "licencia": "license_status",
            "estado": "license_status",
            "querellas": "complaints_count",
            "quejas": "complaints_count",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_patterns.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value:
                        if field == "complaints_count":
                            try:
                                result.complaints_count = int(value)
                            except ValueError:
                                pass
                        elif not getattr(result, field):
                            setattr(result, field, value)
                    break

        rows = page.query_selector_all("table tr")
        if len(rows) >= 2:
            cells = rows[1].query_selector_all("td")
            if cells:
                values = [(c.inner_text() or "").strip() for c in cells]
                if len(values) >= 1 and not result.company_name:
                    result.company_name = values[0]
                if len(values) >= 2 and not result.license_status:
                    result.license_status = values[1]
                if len(values) >= 3 and result.complaints_count == 0:
                    try:
                        result.complaints_count = int(values[2])
                    except ValueError:
                        pass

        return result
