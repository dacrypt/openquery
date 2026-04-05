"""Florida DHSMV vehicle title/registration check source.

Queries the Florida Department of Highway Safety and Motor Vehicles (DHSMV)
Motor Vehicle Check portal for title status, brand history, odometer reading,
and registration events.

Free public service — no login or CAPTCHA required.

Flow:
1. Navigate to https://services.flhsmv.gov/mvcheckweb/
2. Select search type (VIN or license plate)
3. Fill the input field
4. Submit the form
5. Wait for results
6. Parse title status, brand history, odometer, registration, and vehicle info
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.us.fl_dmv import FlDmvResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

FL_DMV_URL = "https://services.flhsmv.gov/mvcheckweb/"


@register
class FlDmvSource(BaseSource):
    """Query Florida DHSMV for vehicle title and registration records."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="us.fl_dmv",
            display_name="Florida DHSMV — Vehicle Title/Registration Check",
            description=(
                "Florida Department of Highway Safety and Motor Vehicles vehicle check — "
                "title status, brand history, odometer reading, and registration events"
            ),
            country="US",
            url=FL_DMV_URL,
            supported_inputs=[DocumentType.VIN, DocumentType.PLATE],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query Florida DHSMV for vehicle title and registration records."""
        if input.document_type not in (DocumentType.VIN, DocumentType.PLATE):
            raise SourceError("us.fl_dmv", f"Unsupported input type: {input.document_type}")

        value = input.document_number.strip().upper()
        if not value:
            raise SourceError("us.fl_dmv", "VIN or plate number is required")

        # Allow caller to override search_type via extra dict; default by document_type
        search_type = input.extra.get("search_type", "")
        if not search_type:
            search_type = "vin" if input.document_type == DocumentType.VIN else "plate"

        return self._query(value, search_type=search_type, audit=input.audit)

    def _query(self, value: str, search_type: str = "vin", audit: bool = False) -> FlDmvResult:
        """Full flow: launch browser, fill form, parse results."""
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("us.fl_dmv", search_type, value)

        with browser.page(FL_DMV_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                logger.info("Waiting for FL DMV form to load...")

                # Select search type radio (VIN or plate)
                if search_type == "vin":
                    vin_radio = page.locator(
                        "input[type='radio'][value*='VIN'], "
                        "input[type='radio'][id*='vin'], "
                        "input[type='radio'][name*='vin']"
                    ).first
                    try:
                        if vin_radio.is_visible(timeout=5000):
                            vin_radio.check()
                            logger.info("Selected VIN search type")
                    except Exception:
                        logger.debug("VIN radio not found, proceeding with default")
                else:
                    plate_radio = page.locator(
                        "input[type='radio'][value*='plate'], "
                        "input[type='radio'][value*='Plate'], "
                        "input[type='radio'][id*='plate'], "
                        "input[type='radio'][name*='plate']"
                    ).first
                    try:
                        if plate_radio.is_visible(timeout=5000):
                            plate_radio.check()
                            logger.info("Selected plate search type")
                    except Exception:
                        logger.debug("Plate radio not found, proceeding with default")

                # Fill the search input
                search_input = page.locator(
                    "input[type='text'], input[name*='vin'], input[name*='plate'], "
                    "input[id*='vin'], input[id*='plate']"
                ).first
                search_input.wait_for(state="visible", timeout=15000)
                search_input.fill(value)
                logger.info("Filled search field: %s (%s)", value, search_type)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Click submit
                submit_btn = page.locator(
                    "button[type='submit'], "
                    "input[type='submit'], "
                    "button:has-text('Search'), "
                    "button:has-text('Submit'), "
                    "button:has-text('Check')"
                ).first
                submit_btn.click()
                logger.info("Clicked submit button")

                # Wait for results
                page.wait_for_selector(
                    "[class*='result'], [class*='Result'], [id*='result'], "
                    "table, dl, .vehicle-info, h2, h3",
                    timeout=20000,
                )
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_results(page, value, search_type)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("us.fl_dmv", f"Query failed: {e}") from e

    def _parse_results(self, page, value: str, search_type: str) -> FlDmvResult:
        """Parse the DHSMV results page."""
        result = FlDmvResult(
            queried_at=datetime.now(),
            search_type=search_type,
            search_value=value,
        )

        body_text = page.inner_text("body")
        body_lower = body_text.lower()
        details: dict[str, str] = {}

        # Title status
        for phrase in ("title status", "title:"):
            idx = body_lower.find(phrase)
            if idx != -1:
                snippet = body_text[idx: idx + 80].strip()
                result.title_status = snippet
                details["title_status_raw"] = snippet
                break

        # Brand history — look for common brand keywords
        brands: list[str] = []
        brand_keywords = (
            "salvage", "rebuilt", "flood", "lemon", "theft", "junk",
            "dismantled", "non-repairable", "odometer rollback", "fire",
        )
        for kw in brand_keywords:
            if kw in body_lower:
                brands.append(kw.title())
        result.brand_history = brands

        # Odometer
        for phrase in ("odometer", "mileage"):
            idx = body_lower.find(phrase)
            if idx != -1:
                snippet = body_text[idx: idx + 60].strip()
                result.odometer = snippet
                details["odometer_raw"] = snippet
                break

        # Registration status
        for phrase in ("registration status", "registration:", "reg status"):
            idx = body_lower.find(phrase)
            if idx != -1:
                snippet = body_text[idx: idx + 80].strip()
                result.registration_status = snippet
                details["registration_raw"] = snippet
                break

        # Vehicle description — year/make/model typically near top
        for selector in (
            "[class*='vehicle'] h2",
            "[class*='vehicle'] h3",
            "[class*='result'] h2",
            "[class*='result'] h3",
            "h2",
            "h3",
        ):
            try:
                el = page.query_selector(selector)
                if el:
                    text = (el.inner_text() or "").strip()
                    if text and len(text) < 200:
                        result.vehicle_description = text
                        break
            except Exception:
                continue

        result.details = details

        logger.info(
            "FL DMV results — %s=%s, title=%r, brands=%s",
            search_type,
            value,
            result.title_status[:40] if result.title_status else "",
            result.brand_history,
        )
        return result
