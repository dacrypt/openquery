"""Honduras IHSS social security source.

Queries Honduras IHSS (Instituto Hondureño de Seguridad Social) for affiliation status.
Browser-based, no CAPTCHA.

URL: https://www.ihss.hn/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.hn.ihss import HnIhssResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

IHSS_URL = "https://www.ihss.hn/"


@register
class HnIhssSource(BaseSource):
    """Query Honduras IHSS social security affiliation status."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="hn.ihss",
            display_name="IHSS — Seguridad Social (HN)",
            description="Honduras IHSS: social security affiliation status and employer by identity number",  # noqa: E501
            country="HN",
            url=IHSS_URL,
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        identidad = input.document_number.strip()
        if not identidad:
            raise SourceError("hn.ihss", "Identity number is required")
        return self._query(identidad, audit=input.audit)

    def _query(self, identidad: str, audit: bool = False) -> HnIhssResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("hn.ihss", "identidad", identidad)

        with browser.page(IHSS_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    "input[name*='identidad'], input[id*='identidad'], "
                    "input[name*='cedula'], input[name*='dni'], input[type='text']"
                )
                if not search_input:
                    raise SourceError("hn.ihss", "Could not find identity input field")

                search_input.fill(identidad)
                logger.info("Filled identity number: %s", identidad)

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

                result = self._parse_result(page, identidad)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("hn.ihss", f"Query failed: {e}") from e

    def _parse_result(self, page, identidad: str) -> HnIhssResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = HnIhssResult(queried_at=datetime.now(), identidad=identidad)

        field_patterns = {
            "estado": "affiliation_status",
            "afiliacion": "affiliation_status",
            "empleador": "employer",
            "empresa": "employer",
            "patron": "employer",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_patterns.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value and not getattr(result, field):
                        setattr(result, field, value)
                    break

        rows = page.query_selector_all("table tr")
        if len(rows) >= 2:
            cells = rows[1].query_selector_all("td")
            if cells:
                values = [(c.inner_text() or "").strip() for c in cells]
                if len(values) >= 1 and not result.affiliation_status:
                    result.affiliation_status = values[0]
                if len(values) >= 2 and not result.employer:
                    result.employer = values[1]

        return result
