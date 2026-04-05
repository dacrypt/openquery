"""Idaho DMV title + registration status source.

Queries the Idaho Transportation Department's public vehicle services portal
for title and registration status by VIN.  No personal identifying information
is displayed — the service is explicitly public.

Flow (title):
1. Navigate to CheckTitleStatus page
2. Fill VIN input and submit
3. Parse title status from results

Flow (registration):
1. Navigate to CheckRegistration page
2. Fill VIN input and submit
3. Parse registration status from results
"""

from __future__ import annotations

import logging

from openquery.exceptions import SourceError
from openquery.models.us.id_dmv import IdDmvResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

TITLE_URL = "https://dmvonline.itd.idaho.gov/OpenServices/OpenVehicleServices/CheckTitleStatus"
REGISTRATION_URL = "https://dmvonline.itd.idaho.gov/OpenServices/OpenVehicleServices/CheckRegistration"


@register
class IdDmvSource(BaseSource):
    """Query Idaho DMV for vehicle title and registration status."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="us.id_dmv",
            display_name="Idaho DMV — Title & Registration Status",
            description=(
                "Idaho Transportation Department public vehicle services — "
                "checks title and registration status by VIN"
            ),
            country="US",
            url=TITLE_URL,
            supported_inputs=[DocumentType.VIN],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> IdDmvResult:
        """Query Idaho DMV for title and registration status."""
        if input.document_type != DocumentType.VIN:
            raise SourceError("us.id_dmv", f"Unsupported input type: {input.document_type}")

        vin = input.document_number.strip().upper()
        if not vin:
            raise SourceError("us.id_dmv", "VIN is required")

        return self._query(vin, audit=input.audit)

    def _query(self, vin: str, audit: bool = False) -> IdDmvResult:
        """Full flow: check title status, then registration status."""
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("us.id_dmv", "vin", vin)

        result = IdDmvResult(vin=vin)

        try:
            # --- Title status ---
            with browser.page(TITLE_URL) as page:
                if collector:
                    collector.attach(page)

                logger.info("Checking title status for VIN: %s", vin)
                self._fill_and_submit(page, vin, "title")

                if collector:
                    collector.screenshot(page, "title_result")

                self._parse_title(page, result)

            # --- Registration status ---
            with browser.page(REGISTRATION_URL) as page:
                if collector:
                    collector.attach(page)

                logger.info("Checking registration status for VIN: %s", vin)
                self._fill_and_submit(page, vin, "registration")

                if collector:
                    collector.screenshot(page, "registration_result")

                self._parse_registration(page, result)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("us.id_dmv", f"Query failed: {e}") from e

        logger.info(
            "Idaho DMV results — vin=%s, title=%s, registration=%s",
            vin,
            result.title_status,
            result.registration_status,
        )
        return result

    def _fill_and_submit(self, page, vin: str, context: str) -> None:
        """Fill the VIN field and submit the form."""
        vin_input = page.locator(
            "input[name*='vin' i], input[id*='vin' i], "
            "input[placeholder*='VIN' i], input[type='text']"
        ).first
        vin_input.wait_for(state="visible", timeout=15000)
        vin_input.fill(vin)
        logger.info("Filled VIN for %s check: %s", context, vin)

        submit_btn = page.locator(
            "button[type='submit'], "
            "input[type='submit'], "
            "button:has-text('Search'), "
            "button:has-text('Check'), "
            "button:has-text('Submit')"
        ).first
        submit_btn.click()

        # Wait for results to load
        page.wait_for_selector(
            "[class*='result' i], [id*='result' i], "
            "[class*='status' i], [id*='status' i], "
            "table, h2, h3, p",
            timeout=20000,
        )
        page.wait_for_timeout(1500)

    def _parse_title(self, page, result: IdDmvResult) -> None:
        """Parse title status from the results page."""
        body_text = page.inner_text("body")
        result.details["title_raw"] = body_text[:500] if body_text else ""

        # Extract vehicle description if available
        if not result.vehicle_description:
            result.vehicle_description = self._extract_vehicle_description(page, body_text)

        # Extract title status text
        status = self._extract_status_text(page, body_text, "title")
        result.title_status = status
        logger.debug("Title status: %s", status)

    def _parse_registration(self, page, result: IdDmvResult) -> None:
        """Parse registration status from the results page."""
        body_text = page.inner_text("body")
        result.details["registration_raw"] = body_text[:500] if body_text else ""

        # Extract vehicle description if not already set
        if not result.vehicle_description:
            result.vehicle_description = self._extract_vehicle_description(page, body_text)

        # Extract registration status text
        status = self._extract_status_text(page, body_text, "registration")
        result.registration_status = status
        logger.debug("Registration status: %s", status)

    def _extract_status_text(self, page, body_text: str, context: str) -> str:
        """Extract the primary status message from the page."""
        # Try targeted selectors first
        for selector in (
            "[class*='status' i]",
            "[class*='result' i] p",
            "[class*='result' i]",
            "h2",
            "h3",
            "p",
        ):
            try:
                el = page.query_selector(selector)
                if el:
                    text = (el.inner_text() or "").strip()
                    if text and len(text) < 300:
                        return text
            except Exception:
                continue

        # Fall back to first meaningful line of body text
        for line in body_text.splitlines():
            line = line.strip()
            if line and len(line) > 5 and len(line) < 300:
                return line

        return ""

    def _extract_vehicle_description(self, page, body_text: str) -> str:
        """Try to extract vehicle year/make/model from the page."""
        for selector in (
            "[class*='vehicle' i]",
            "[class*='description' i]",
            "[class*='detail' i] h3",
            "[class*='detail' i] p",
        ):
            try:
                el = page.query_selector(selector)
                if el:
                    text = (el.inner_text() or "").strip()
                    if text and len(text) < 200:
                        return text
            except Exception:
                continue

        return ""
