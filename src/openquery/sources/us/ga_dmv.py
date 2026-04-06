"""Georgia DRIVES vehicle title and insurance status source.

Queries the Georgia DRIVES eServices portal for:
- Title status (via VIN): https://eservices.drives.ga.gov/?Link=TitleStatus
  Returns title validity, ELT lienholder, brand info.
- Insurance verification (via plate): https://eservices.drives.ga.gov/?link=VhcStatus
  Returns insurance verification status.

Flow (title):
1. Navigate to TitleStatus URL
2. Fill the VIN input field
3. Submit the form
4. Wait for and parse results

Flow (insurance):
1. Navigate to VhcStatus URL
2. Fill the plate input field
3. Submit the form
4. Wait for and parse results
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.us.ga_dmv import GaDmvResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

GA_DMV_TITLE_URL = "https://eservices.drives.ga.gov/?Link=TitleStatus"
GA_DMV_INSURANCE_URL = "https://eservices.drives.ga.gov/?link=VhcStatus"


@register
class GaDmvSource(BaseSource):
    """Query Georgia DRIVES for vehicle title status and insurance verification."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="us.ga_dmv",
            display_name="Georgia DRIVES — Title & Insurance Status",
            description=(
                "Georgia DRIVES eServices — vehicle title status (VIN) "
                "and insurance verification (plate)"
            ),
            country="US",
            url="https://eservices.drives.ga.gov/",
            supported_inputs=[DocumentType.VIN, DocumentType.PLATE, DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query Georgia DRIVES for title or insurance status."""
        search_type = input.extra.get("search_type", "title")

        if input.document_type == DocumentType.VIN or (
            input.document_type == DocumentType.CUSTOM and search_type == "title"
        ):
            value = input.document_number.strip().upper()
            if not value:
                raise SourceError("us.ga_dmv", "VIN is required for title search")
            return self._query_title(value, audit=input.audit)

        if input.document_type == DocumentType.PLATE or (
            input.document_type == DocumentType.CUSTOM and search_type == "insurance"
        ):
            value = input.document_number.strip().upper()
            if not value:
                raise SourceError("us.ga_dmv", "Plate is required for insurance search")
            return self._query_insurance(value, audit=input.audit)

        raise SourceError(
            "us.ga_dmv",
            f"Unsupported input type: {input.document_type}. "
            "Use VIN for title search or PLATE for insurance search. "
            "For CUSTOM type, set extra.search_type to 'title' or 'insurance'.",
        )

    def _query_title(self, vin: str, audit: bool = False) -> GaDmvResult:
        """Query title status by VIN."""
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("us.ga_dmv", "vin", vin)

        with browser.page(GA_DMV_TITLE_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                # The form has radio buttons: "Title Number" (default) and "VIN".
                # Click VIN radio first so the textbox is labeled for VIN input.
                logger.info("Waiting for GA DRIVES title status form...")
                vin_radio = page.get_by_role("radio", name="VIN")
                vin_radio.wait_for(state="visible", timeout=15000)
                vin_radio.click()
                logger.info("Selected VIN radio button")

                # After clicking VIN radio the textbox label changes to "VIN *"
                vin_input = page.get_by_role("textbox")
                vin_input.wait_for(state="visible", timeout=5000)
                vin_input.fill(vin)
                logger.info("Filled VIN: %s", vin)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit button text: "Get Title Status"
                submit_btn = page.get_by_role("button", name="Get Title Status")
                submit_btn.click()
                logger.info("Clicked Get Title Status button")

                page.wait_for_selector(
                    "[class*='result' i], [id*='result' i], "
                    "table, h2, h3, p, div[class*='status' i]",
                    timeout=20000,
                )
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_title_results(page, vin)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("us.ga_dmv", f"Title query failed: {e}") from e

    def _query_insurance(self, plate: str, audit: bool = False) -> GaDmvResult:
        """Query insurance verification by plate."""
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("us.ga_dmv", "plate", plate)

        with browser.page(GA_DMV_INSURANCE_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                logger.info("Waiting for insurance search form...")
                plate_input = page.locator(
                    "input[name*='plate' i], input[id*='plate' i], "
                    "input[name*='tag' i], input[id*='tag' i], "
                    "input[type='text']"
                ).first
                plate_input.wait_for(state="visible", timeout=15000)
                plate_input.fill(plate)
                logger.info("Filled plate: %s", plate)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit_btn = page.locator(
                    "button[type='submit'], input[type='submit'], "
                    "button:has-text('Search'), button:has-text('Submit'), "
                    "button:has-text('Check'), a:has-text('Search')"
                ).first
                submit_btn.click()
                logger.info("Clicked submit button")

                page.wait_for_selector(
                    "[class*='result' i], [id*='result' i], "
                    "table, h2, h3, p, div[class*='status' i]",
                    timeout=20000,
                )
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_insurance_results(page, plate)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("us.ga_dmv", f"Insurance query failed: {e}") from e

    def _parse_title_results(self, page, vin: str) -> GaDmvResult:
        """Parse the title status results page."""
        result = GaDmvResult(
            queried_at=datetime.now(),
            search_type="title",
            search_value=vin,
        )

        body_text = page.inner_text("body")
        body_lower = body_text.lower()
        details: dict[str, str] = {}

        # Title status
        for phrase in ("title is valid", "valid title", "title valid"):
            if phrase in body_lower:
                result.title_status = "valid"
                details["title_status"] = "Valid"
                break
        if not result.title_status:
            for phrase in ("no title found", "title not found", "no record"):
                if phrase in body_lower:
                    result.title_status = "not_found"
                    details["title_status"] = "Not found"
                    break

        # ELT lienholder
        for selector in (
            "[class*='lien' i]",
            "[id*='lien' i]",
            "td:has-text('Lienholder') + td",
            "td:has-text('Lien') + td",
        ):
            try:
                el = page.query_selector(selector)
                if el:
                    text = (el.inner_text() or "").strip()
                    if text:
                        result.lienholder = text
                        details["lienholder"] = text
                        break
            except Exception:
                continue

        # Brand info
        for selector in (
            "[class*='brand' i]",
            "[id*='brand' i]",
            "td:has-text('Brand') + td",
            "td:has-text('Title Brand') + td",
        ):
            try:
                el = page.query_selector(selector)
                if el:
                    text = (el.inner_text() or "").strip()
                    if text:
                        result.brand_info = text
                        details["brand_info"] = text
                        break
            except Exception:
                continue

        # Vehicle description
        for selector in (
            "[class*='vehicle' i]",
            "[id*='vehicle' i]",
            "td:has-text('Year') + td",
            "td:has-text('Make') + td",
        ):
            try:
                el = page.query_selector(selector)
                if el:
                    text = (el.inner_text() or "").strip()
                    if text:
                        result.vehicle_description = text
                        details["vehicle_description"] = text
                        break
            except Exception:
                continue

        result.details = details
        logger.info(
            "GA DMV title results — vin=%s, status=%s, lienholder=%s",
            vin,
            result.title_status,
            result.lienholder,
        )
        return result

    def _parse_insurance_results(self, page, plate: str) -> GaDmvResult:
        """Parse the insurance verification results page."""
        result = GaDmvResult(
            queried_at=datetime.now(),
            search_type="insurance",
            search_value=plate,
        )

        body_text = page.inner_text("body")
        body_lower = body_text.lower()
        details: dict[str, str] = {}

        # Insurance status — check negative phrases first to avoid "insured" matching "uninsured"
        _uninsured_phrases = ("no insurance", "uninsured", "no coverage", "not insured")
        _active_phrases = ("insurance is active", "active insurance", "insured", "coverage active")
        if any(phrase in body_lower for phrase in _uninsured_phrases):
            result.insurance_status = "uninsured"
            details["insurance_status"] = "Uninsured"
        elif any(phrase in body_lower for phrase in _active_phrases):
            result.insurance_status = "active"
            details["insurance_status"] = "Active"

        # Vehicle description
        for selector in (
            "[class*='vehicle' i]",
            "[id*='vehicle' i]",
            "td:has-text('Year') + td",
            "td:has-text('Make') + td",
        ):
            try:
                el = page.query_selector(selector)
                if el:
                    text = (el.inner_text() or "").strip()
                    if text:
                        result.vehicle_description = text
                        details["vehicle_description"] = text
                        break
            except Exception:
                continue

        result.details = details
        logger.info(
            "GA DMV insurance results — plate=%s, status=%s",
            plate,
            result.insurance_status,
        )
        return result
