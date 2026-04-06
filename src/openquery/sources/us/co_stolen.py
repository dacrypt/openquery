"""Colorado stolen vehicle check source.

Queries the Colorado Department of Public Safety Motor Vehicle Verification
System (MVVS) to check whether a vehicle has been reported stolen in the
Colorado Crime Information Center (CCIC).

Public portal — no login required.

Flow:
1. Navigate to https://secure.colorado.gov/apps/dps/mvvs/public/entry.jsf
2. Wait for the form to load
3. Fill the VIN input field
4. Fill the model year field
5. Click the search/submit button
6. Wait for results
7. Parse the page for stolen status
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.us.co_stolen import CoStolenResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CO_STOLEN_URL = "https://secure.colorado.gov/apps/dps/mvvs/public/entry.jsf"


@register
class CoStolenSource(BaseSource):
    """Query Colorado MVVS for stolen vehicle records."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="us.co_stolen",
            display_name="Colorado MVVS — Stolen Vehicle Check",
            description="Colorado Department of Public Safety Motor Vehicle Verification System — checks if a vehicle is reported stolen in the Colorado Crime Information Center",  # noqa: E501
            country="US",
            url=CO_STOLEN_URL,
            supported_inputs=[DocumentType.VIN],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query Colorado MVVS for stolen vehicle status."""
        if input.document_type != DocumentType.VIN:
            raise SourceError("us.co_stolen", f"Unsupported input type: {input.document_type}")

        vin = input.document_number.strip().upper()
        if not vin:
            raise SourceError("us.co_stolen", "VIN is required")

        year = input.extra.get("year", "")
        if not year:
            raise SourceError(
                "us.co_stolen", "Model year is required (pass as extra={'year': '2020'})"
            )

        return self._query(vin, str(year), audit=input.audit)

    def _query(self, vin: str, year: str, audit: bool = False) -> CoStolenResult:
        """Full flow: launch browser, fill form, parse results."""
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("us.co_stolen", "vin", vin)

        with browser.page(CO_STOLEN_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                logger.info("Waiting for Colorado MVVS form...")

                # Wait for VIN input
                vin_input = page.locator(
                    "input[id*='vin'], input[name*='vin'], input[id*='VIN'], input[name*='VIN']"
                ).first
                vin_input.wait_for(state="visible", timeout=15000)

                # Fill VIN
                vin_input.fill(vin)
                logger.info("Filled VIN: %s", vin)

                # Fill model year
                year_input = page.locator(
                    "input[id*='year'], input[name*='year'], "
                    "input[id*='Year'], input[name*='Year'], "
                    "input[id*='modelYear'], input[name*='modelYear']"
                ).first
                try:
                    if year_input.is_visible(timeout=5000):
                        year_input.fill(year)
                        logger.info("Filled model year: %s", year)
                except Exception:
                    logger.debug(
                        "Year input not found by standard selectors, trying select element"
                    )
                    year_select = page.locator(
                        "select[id*='year'], select[name*='year'], "
                        "select[id*='Year'], select[name*='Year']"
                    ).first
                    try:
                        if year_select.is_visible(timeout=3000):
                            year_select.select_option(year)
                            logger.info("Selected model year: %s", year)
                    except Exception:
                        logger.warning("Could not fill model year field")

                if collector:
                    collector.screenshot(page, "form_filled")

                # Click submit button
                submit_btn = page.locator(
                    "input[type='submit'], "
                    "button[type='submit'], "
                    "button:has-text('Search'), "
                    "button:has-text('Submit'), "
                    "button:has-text('Check')"
                ).first
                submit_btn.click()
                logger.info("Clicked submit button")

                # Wait for results
                page.wait_for_selector(
                    "[class*='result'], [id*='result'], "
                    "[class*='Result'], [id*='Result'], "
                    "table, h2, h3, p",
                    timeout=20000,
                )
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_results(page, vin, year)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("us.co_stolen", f"Query failed: {e}") from e

    def _parse_results(self, page, vin: str, year: str) -> CoStolenResult:
        """Parse the MVVS results page for stolen status."""
        result = CoStolenResult(queried_at=datetime.now(), vin=vin, model_year=year)
        details: dict[str, str] = {}

        body_text = page.inner_text("body").lower()

        # Check for explicit stolen indicators
        stolen_phrases = (
            "reported stolen",
            "vehicle is stolen",
            "stolen vehicle",
            "theft record",
            "vehicle has been reported",
        )
        not_stolen_phrases = (
            "not reported stolen",
            "no record",
            "no theft",
            "not stolen",
            "vehicle is not",
            "clear",
        )

        if any(phrase in body_text for phrase in stolen_phrases):
            if any(phrase in body_text for phrase in not_stolen_phrases):
                result.is_stolen = False
                details["stolen_status"] = "not stolen"
            else:
                result.is_stolen = True
                details["stolen_status"] = "reported stolen"
        elif any(phrase in body_text for phrase in not_stolen_phrases):
            result.is_stolen = False
            details["stolen_status"] = "not stolen"

        # Capture visible status message from page
        for selector in (
            "[id*='result'] p",
            "[class*='result'] p",
            "[id*='message']",
            "[class*='message']",
            "h2",
            "h3",
            "p",
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
            "Colorado MVVS results — vin=%s, year=%s, is_stolen=%s",
            vin,
            year,
            result.is_stolen,
        )
        return result
