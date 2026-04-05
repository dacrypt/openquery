"""Arizona MVD title/lien status source.

Queries the Arizona Motor Vehicle Division's title check express service via
headless browser. No login required.

Flow:
1. Navigate to https://azmvdnow.gov/
2. Find and click the Title / Check Title Status express service
3. Fill the VIN input field
4. Submit the form
5. Wait for and parse the results (title status, lien status, vehicle description)
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.us.az_mvd import AzMvdResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

AZ_MVD_URL = "https://azmvdnow.gov/"


@register
class AzMvdSource(BaseSource):
    """Query Arizona MVD for title and lien status by VIN."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="us.az_mvd",
            display_name="Arizona MVD — Title & Lien Status",
            description="Arizona Motor Vehicle Division title check — returns title status and lien information for a vehicle by VIN",
            country="US",
            url=AZ_MVD_URL,
            supported_inputs=[DocumentType.VIN],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query Arizona MVD for title and lien status."""
        if input.document_type != DocumentType.VIN:
            raise SourceError("us.az_mvd", f"Unsupported input type: {input.document_type}")

        vin = input.document_number.strip().upper()
        if not vin:
            raise SourceError("us.az_mvd", "VIN is required")

        return self._query(vin, audit=input.audit)

    def _query(self, vin: str, audit: bool = False) -> AzMvdResult:
        """Full flow: launch browser, navigate to title check, fill form, parse results."""
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("us.az_mvd", "vin", vin)

        with browser.page(AZ_MVD_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                # Look for the Title / Check Title Status express service link
                logger.info("Looking for title check express service link...")
                title_link = page.locator(
                    "a:has-text('Title'), "
                    "a:has-text('Check Title'), "
                    "a:has-text('Title Status'), "
                    "button:has-text('Title'), "
                    "[href*='title']"
                ).first
                try:
                    if title_link.is_visible(timeout=5000):
                        title_link.click()
                        logger.info("Clicked title check link")
                        page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    logger.debug("No title link found on homepage, proceeding")

                if collector:
                    collector.screenshot(page, "title_page")

                # Wait for VIN input
                logger.info("Waiting for VIN input...")
                vin_input = page.locator(
                    "input[name*='vin' i], "
                    "input[id*='vin' i], "
                    "input[placeholder*='VIN' i], "
                    "input[placeholder*='Vehicle Identification' i], "
                    "input[type='text']"
                ).first
                vin_input.wait_for(state="visible", timeout=15000)

                # Fill VIN
                vin_input.fill(vin)
                logger.info("Filled VIN: %s", vin)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Click submit button
                submit_btn = page.locator(
                    "button[type='submit'], "
                    "input[type='submit'], "
                    "button:has-text('Search'), "
                    "button:has-text('Check'), "
                    "button:has-text('Submit'), "
                    "button:has-text('Look Up')"
                ).first
                submit_btn.click()
                logger.info("Clicked submit button")

                # Wait for results
                page.wait_for_selector(
                    "[class*='result' i], [class*='title' i], [class*='lien' i], "
                    "[id*='result' i], h2, h3, table",
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
                raise SourceError("us.az_mvd", f"Query failed: {e}") from e

    def _parse_results(self, page, vin: str) -> AzMvdResult:
        """Parse the Arizona MVD title check results page."""
        result = AzMvdResult(queried_at=datetime.now(), vin=vin)
        details: dict[str, str] = {}

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        # Extract title status
        title_status = ""
        for phrase in (
            "title status",
            "title:",
        ):
            idx = body_lower.find(phrase)
            if idx != -1:
                # Grab up to 80 chars after the label
                snippet = body_text[idx : idx + 80].strip()
                first_line = snippet.splitlines()[0] if snippet else snippet
                if ":" in first_line:
                    title_status = first_line.split(":", 1)[1].strip()[:60]
                if title_status:
                    break

        if title_status:
            result.title_status = title_status
            details["title_status"] = title_status
        elif "clear" in body_lower:
            result.title_status = "Clear"
            details["title_status"] = "Clear"
        elif "salvage" in body_lower:
            result.title_status = "Salvage"
            details["title_status"] = "Salvage"
        elif "rebuilt" in body_lower:
            result.title_status = "Rebuilt"
            details["title_status"] = "Rebuilt"

        # Extract lien status
        lien_status = ""
        if "no lien" in body_lower or "no liens" in body_lower:
            lien_status = "No Lien"
        elif "lien" in body_lower:
            lien_status = "Lien Reported"

        if lien_status:
            result.lien_status = lien_status
            details["lien_status"] = lien_status

        # Extract vehicle description from common selectors
        for selector in (
            "[class*='vehicle' i]",
            "[class*='description' i]",
            "table td",
            "h2",
            "h3",
        ):
            try:
                el = page.query_selector(selector)
                if el:
                    text = (el.inner_text() or "").strip()
                    if text and len(text) < 200 and len(text) > 5:
                        result.vehicle_description = text
                        details["vehicle_description"] = text
                        break
            except Exception:
                continue

        result.details = details

        logger.info(
            "AzMvd results — vin=%s, title_status=%s, lien_status=%s",
            vin,
            result.title_status,
            result.lien_status,
        )
        return result
