"""Louisiana OMV title verification source.

Queries the Louisiana Office of Motor Vehicles title verification portal via
headless browser. Checks whether a Louisiana vehicle title is valid by VIN or
title number.

No login required, 24/7 access.

Flow:
1. Navigate to https://la.accessgov.com/title-verification/Forms/Page/title-verification/check
2. Wait for the form to load
3. Fill VIN or title number into the search field
4. Submit the form
5. Wait for and parse the result
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.us.la_title import LaTitleResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

LA_TITLE_URL = "https://la.accessgov.com/title-verification/Forms/Page/title-verification/check"


@register
class LaTitleSource(BaseSource):
    """Query Louisiana OMV for vehicle title validity by VIN or title number."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="us.la_title",
            display_name="Louisiana OMV — Title Verification",
            description="Louisiana Office of Motor Vehicles title verification — checks if a vehicle title is valid by VIN or title number",
            country="US",
            url=LA_TITLE_URL,
            supported_inputs=[DocumentType.VIN, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query Louisiana OMV title verification portal."""
        if input.document_type not in (DocumentType.VIN, DocumentType.CUSTOM):
            raise SourceError("us.la_title", f"Unsupported input type: {input.document_type}")

        search_value = input.document_number.strip().upper()
        if not search_value:
            raise SourceError("us.la_title", "VIN or title number is required")

        search_type = "vin" if input.document_type == DocumentType.VIN else "title_number"
        return self._query(search_value, search_type, audit=input.audit)

    def _query(self, search_value: str, search_type: str, audit: bool = False) -> LaTitleResult:
        """Full flow: launch browser, fill form, parse results."""
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("us.la_title", search_type, search_value)

        with browser.page(LA_TITLE_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                # Wait for the search input to appear
                logger.info("Waiting for Louisiana title verification form...")
                search_input = page.locator(
                    "input[name*='vin'], input[id*='vin'], "
                    "input[name*='title'], input[id*='title'], "
                    "input[placeholder*='VIN'], input[placeholder*='Title'], "
                    "input[type='text']"
                ).first
                search_input.wait_for(state="visible", timeout=15000)

                # Fill the search value
                search_input.fill(search_value)
                logger.info("Filled search value: %s (type=%s)", search_value, search_type)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Click submit button
                submit_btn = page.locator(
                    "button[type='submit'], "
                    "input[type='submit'], "
                    "button:has-text('Search'), "
                    "button:has-text('Check'), "
                    "button:has-text('Verify'), "
                    "button:has-text('Submit')"
                ).first
                submit_btn.click()
                logger.info("Clicked submit button")

                # Wait for results
                page.wait_for_selector(
                    "[class*='result'], [class*='Result'], [id*='result'], "
                    "[class*='valid'], [class*='invalid'], "
                    "h2, h3, p",
                    timeout=20000,
                )
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_results(page, search_value, search_type)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("us.la_title", f"Query failed: {e}") from e

    def _parse_results(self, page, search_value: str, search_type: str) -> LaTitleResult:
        """Parse the title verification results page."""
        result = LaTitleResult(
            queried_at=datetime.now(),
            search_value=search_value,
            search_type=search_type,
        )

        body_text = page.inner_text("body").lower()
        details: dict[str, str] = {}

        # Detect valid/invalid title status — check negative phrases first to avoid
        # false positives (e.g. "no title found" contains "title found")
        if any(phrase in body_text for phrase in (
            "title is not valid",
            "invalid title",
            "no title found",
            "not found",
            "no record",
        )):
            result.title_valid = False
            details["status"] = "not_found"
        elif any(phrase in body_text for phrase in (
            "title is valid",
            "valid title",
            "title found",
            "active title",
        )):
            result.title_valid = True
            details["status"] = "valid"

        # Try to capture vehicle description
        for selector in (
            "[class*='vehicle']",
            "[class*='result'] p",
            "[class*='description']",
        ):
            try:
                el = page.query_selector(selector)
                if el:
                    text = (el.inner_text() or "").strip()
                    if text and len(text) < 300:
                        result.vehicle_description = text
                        break
            except Exception:
                continue

        # Capture visible status message
        for selector in (
            "[class*='result'] h2",
            "[class*='result'] h3",
            "[class*='result'] p",
            "[class*='message']",
            "h2",
            "h3",
        ):
            try:
                el = page.query_selector(selector)
                if el:
                    text = (el.inner_text() or "").strip()
                    if text and len(text) < 300:
                        result.status_message = text
                        break
            except Exception:
                continue

        result.details = details

        logger.info(
            "Louisiana title check — value=%s, type=%s, valid=%s",
            search_value,
            search_type,
            result.title_valid,
        )
        return result
