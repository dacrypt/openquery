"""Paraguay MRE consular/passport status source.

Queries MRE (Ministerio de Relaciones Exteriores) for passport
status data by passport number.

URL: https://www.mre.gov.py/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.py.mre import PyMreResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

MRE_URL = "https://www.mre.gov.py/"


@register
class PyMreSource(BaseSource):
    """Query Paraguay MRE for passport/consular status."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="py.mre",
            display_name="MRE — Estado Pasaporte Paraguay",
            description=(
                "Paraguay MRE consular registry: passport status "
                "and consular information by passport number"
            ),
            country="PY",
            url=MRE_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query MRE for passport status."""
        passport_number = input.extra.get("passport_number", "") or input.document_number
        if not passport_number:
            raise SourceError("py.mre", "passport_number is required")
        return self._query(passport_number.strip(), audit=input.audit)

    def _query(self, passport_number: str, audit: bool = False) -> PyMreResult:
        """Full flow: launch browser, fill form, parse results."""
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("py.mre", "passport_number", passport_number)

        with browser.page(MRE_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                search_input = page.query_selector(
                    'input[id*="pasaporte"], input[name*="pasaporte"], '
                    'input[id*="passport"], input[name*="passport"], '
                    'input[id*="numero"], input[name*="numero"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("py.mre", "Could not find passport number input field")

                search_input.fill(passport_number)
                logger.info("Filled passport number: %s", passport_number)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button:has-text("Consultar"), button:has-text("Buscar")'
                )
                if submit:
                    submit.click()
                else:
                    search_input.press("Enter")

                page.wait_for_timeout(3000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, passport_number)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("py.mre", f"Query failed: {e}") from e

    def _parse_result(self, page, passport_number: str) -> PyMreResult:
        """Parse passport status data from the page DOM."""
        body_text = page.inner_text("body")
        result = PyMreResult(passport_number=passport_number)
        details: dict[str, str] = {}

        field_map = {
            "estado": "status",
            "status": "status",
            "estado del pasaporte": "status",
            "passport status": "status",
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
        logger.info("MRE result — passport=%s, status=%s", passport_number, result.status)
        return result
