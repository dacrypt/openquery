"""NICB VINCheck source — stolen/salvage vehicle check.

Queries the National Insurance Crime Bureau's VINCheck service via headless
browser.  The service checks whether a vehicle has been reported stolen (and
not recovered) or declared salvage.

Free public service — 5 lookups per 24 h per IP address.

Flow:
1. Navigate to https://www.nicb.org/vincheck
2. Wait for the form to load
3. Fill the VIN input field
4. Accept the terms/conditions checkbox if present
5. Click the search/submit button
6. Wait for results
7. Parse the page body for theft and salvage status
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.us.nicb_vincheck import NicbVincheckResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

NICB_URL = "https://www.nicb.org/vincheck"


@register
class NicbVincheckSource(BaseSource):
    """Query NICB VINCheck for stolen/salvage vehicle records."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="us.nicb_vincheck",
            display_name="NICB VINCheck — Stolen/Salvage Check",
            description="National Insurance Crime Bureau VINCheck — checks if a vehicle was reported stolen or declared salvage",
            country="US",
            url=NICB_URL,
            supported_inputs=[DocumentType.VIN],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=5,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query NICB VINCheck for theft and salvage records."""
        if input.document_type != DocumentType.VIN:
            raise SourceError("us.nicb_vincheck", f"Unsupported input type: {input.document_type}")

        vin = input.document_number.strip().upper()
        if not vin:
            raise SourceError("us.nicb_vincheck", "VIN is required")

        return self._query(vin, audit=input.audit)

    def _query(self, vin: str, audit: bool = False) -> NicbVincheckResult:
        """Full flow: launch browser, fill form, parse results."""
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("us.nicb_vincheck", "vin", vin)

        with browser.page(NICB_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                # Wait for the VIN input to appear
                logger.info("Waiting for VINCheck form...")
                vin_input = page.locator("input[name='vin'], input[id*='vin'], input[placeholder*='VIN'], input[type='text']").first
                vin_input.wait_for(state="visible", timeout=15000)

                # Fill VIN
                vin_input.fill(vin)
                logger.info("Filled VIN: %s", vin)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Accept terms checkbox if present
                terms_checkbox = page.locator(
                    "input[type='checkbox'][name*='term'], "
                    "input[type='checkbox'][id*='term'], "
                    "input[type='checkbox'][name*='agree'], "
                    "input[type='checkbox'][id*='agree']"
                ).first
                try:
                    if terms_checkbox.is_visible(timeout=3000):
                        if not terms_checkbox.is_checked():
                            terms_checkbox.check()
                            logger.info("Accepted terms checkbox")
                except Exception:
                    logger.debug("No terms checkbox found or already accepted")

                # Click submit button
                submit_btn = page.locator(
                    "button[type='submit'], "
                    "input[type='submit'], "
                    "button:has-text('Search'), "
                    "button:has-text('Check'), "
                    "button:has-text('Submit')"
                ).first
                submit_btn.click()
                logger.info("Clicked submit button")

                # Wait for results to appear
                page.wait_for_selector(
                    "[class*='result'], [class*='Result'], [id*='result'], "
                    "[class*='theft'], [class*='salvage'], "
                    "h2, h3, p",
                    timeout=20000,
                )
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_results(page, vin)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("us.nicb_vincheck", f"Query failed: {e}") from e

    def _parse_results(self, page, vin: str) -> NicbVincheckResult:
        """Parse the VINCheck results page."""
        result = NicbVincheckResult(queried_at=datetime.now(), vin=vin)

        body_text = page.inner_text("body").lower()
        details: list[str] = []

        # Check for theft records
        if "theft" in body_text:
            if any(phrase in body_text for phrase in (
                "theft record",
                "reported stolen",
                "stolen vehicle",
                "theft has been reported",
            )):
                if any(phrase in body_text for phrase in (
                    "no theft",
                    "no record of theft",
                    "no theft record",
                    "0 theft",
                )):
                    result.theft_records_found = False
                    details.append("No theft records found")
                else:
                    result.theft_records_found = True
                    details.append("Theft record found")
            else:
                details.append("Theft status checked")

        # Check for salvage records
        if "salvage" in body_text:
            if any(phrase in body_text for phrase in (
                "salvage record",
                "declared salvage",
                "salvage title",
                "salvage has been reported",
            )):
                if any(phrase in body_text for phrase in (
                    "no salvage",
                    "no record of salvage",
                    "no salvage record",
                    "0 salvage",
                )):
                    result.salvage_records_found = False
                    details.append("No salvage records found")
                else:
                    result.salvage_records_found = True
                    details.append("Salvage record found")
            else:
                details.append("Salvage status checked")

        # Capture the visible status message from the page
        for selector in (
            "[class*='result'] h2",
            "[class*='result'] h3",
            "[class*='result'] p",
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
            "VINCheck results — vin=%s, theft=%s, salvage=%s",
            vin,
            result.theft_records_found,
            result.salvage_records_found,
        )
        return result
