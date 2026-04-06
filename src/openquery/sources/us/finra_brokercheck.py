"""FINRA BrokerCheck source — US broker/advisor verification.

Queries FINRA BrokerCheck for broker and investment advisor
registration and disciplinary information.

Source: https://brokercheck.finra.org/
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.us.finra_brokercheck import FinraBrokercheckResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

FINRA_URL = "https://brokercheck.finra.org/"


@register
class FinraBrokercheckSource(BaseSource):
    """Query FINRA BrokerCheck for broker/advisor registration and status."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="us.finra_brokercheck",
            display_name="FINRA BrokerCheck",
            description="FINRA BrokerCheck: broker/advisor CRD number, registration status, and disciplinary history",  # noqa: E501
            country="US",
            url=FINRA_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = (
            input.extra.get("broker_name", "")
            or input.extra.get("crd_number", "")
            or input.document_number
        ).strip()
        if not search_term:
            raise SourceError(
                "us.finra_brokercheck",
                "Broker name or CRD number required (pass via extra.broker_name, extra.crd_number, or document_number)",  # noqa: E501
            )
        return self._query(search_term, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> FinraBrokercheckResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("us.finra_brokercheck", "broker", search_term)

        with browser.page(FINRA_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(2000)

                search_input = page.locator(
                    'input[placeholder*="Search"], input[placeholder*="search"], '
                    'input[aria-label*="search"], input[type="search"], '
                    'input[type="text"]'
                ).first
                if search_input:
                    search_input.fill(search_term)
                    logger.info("Searching FINRA BrokerCheck for: %s", search_term)
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
                raise SourceError("us.finra_brokercheck", f"Query failed: {e}") from e

    def _parse_result(self, page, search_term: str) -> FinraBrokercheckResult:
        body_text = page.inner_text("body")
        result = FinraBrokercheckResult(queried_at=datetime.now(), search_term=search_term)

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            if "crd" in lower and "#" in stripped and not result.crd_number:
                parts = stripped.split("#")
                if len(parts) > 1:
                    result.crd_number = parts[1].strip().split()[0]
            elif "registered" in lower or "not registered" in lower:
                result.status = "Registered" if "not registered" not in lower else "Not Registered"
            elif len(stripped) > 3 and stripped.isupper() and not result.broker_name:
                result.broker_name = stripped.title()

        return result
