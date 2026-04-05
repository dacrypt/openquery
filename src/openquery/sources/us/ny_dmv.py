"""New York DMV title/lien status source.

Queries the New York State DMV Title Status portal for vehicle title and lien
information using VIN, model year, and make.

No login required, no CAPTCHA.

Flow:
1. Navigate to https://process.dmv.ny.gov/titlestatus/
2. Wait for the form to load
3. Fill VIN, model year, and make fields
4. Submit the form
5. Parse title status and lien status from results
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.us.ny_dmv import NyDmvResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

NY_DMV_URL = "https://process.dmv.ny.gov/titlestatus/"


@register
class NyDmvSource(BaseSource):
    """Query New York DMV for vehicle title and lien status."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="us.ny_dmv",
            display_name="New York DMV — Title/Lien Status",
            description="New York State DMV title and lien status lookup by VIN, model year, and make",  # noqa: E501
            country="US",
            url=NY_DMV_URL,
            supported_inputs=[DocumentType.VIN],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query NY DMV for title and lien status."""
        if input.document_type != DocumentType.VIN:
            raise SourceError("us.ny_dmv", f"Unsupported input type: {input.document_type}")

        vin = input.document_number.strip().upper()
        if not vin:
            raise SourceError("us.ny_dmv", "VIN is required")

        year = str(input.extra.get("year", "")).strip()
        make = str(input.extra.get("make", "")).strip().upper()

        if not year:
            raise SourceError("us.ny_dmv", "Model year is required (extra.year)")
        if not make:
            raise SourceError("us.ny_dmv", "Make is required (extra.make)")

        return self._query(vin, year, make, audit=input.audit)

    def _query(self, vin: str, year: str, make: str, audit: bool = False) -> NyDmvResult:
        """Full flow: launch browser, fill form, parse results."""
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("us.ny_dmv", "vin", vin)

        with browser.page(NY_DMV_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                logger.info("Waiting for NY DMV title status form...")

                # Wait for VIN input
                vin_input = page.locator(
                    "input[name*='vin' i], input[id*='vin' i], input[placeholder*='vin' i]"
                ).first
                vin_input.wait_for(state="visible", timeout=15000)

                # Fill VIN
                vin_input.fill(vin)
                logger.info("Filled VIN: %s", vin)

                # Fill model year
                year_input = page.locator(
                    "input[name*='year' i], input[id*='year' i], input[placeholder*='year' i], "
                    "select[name*='year' i], select[id*='year' i]"
                ).first
                tag = year_input.evaluate("el => el.tagName.toLowerCase()")
                if tag == "select":
                    year_input.select_option(year)
                else:
                    year_input.fill(year)
                logger.info("Filled model year: %s", year)

                # Fill make
                make_input = page.locator(
                    "input[name*='make' i], input[id*='make' i], input[placeholder*='make' i], "
                    "select[name*='make' i], select[id*='make' i]"
                ).first
                tag = make_input.evaluate("el => el.tagName.toLowerCase()")
                if tag == "select":
                    make_input.select_option(make)
                else:
                    make_input.fill(make)
                logger.info("Filled make: %s", make)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit_btn = page.locator(
                    "button[type='submit'], "
                    "input[type='submit'], "
                    "button:has-text('Search'), "
                    "button:has-text('Submit'), "
                    "button:has-text('Check')"
                ).first
                submit_btn.click()
                logger.info("Submitted NY DMV form")

                # Wait for results
                page.wait_for_selector(
                    "[class*='result' i], [id*='result' i], "
                    "table, dl, .title-status, .lien-status, "
                    "h2, h3",
                    timeout=20000,
                )
                page.wait_for_timeout(1500)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_results(page, vin, year, make)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("us.ny_dmv", f"Query failed: {e}") from e

    def _parse_results(self, page, vin: str, year: str, make: str) -> NyDmvResult:
        """Parse the NY DMV title status results page."""
        result = NyDmvResult(
            queried_at=datetime.now(),
            vin=vin,
            make=make,
            model_year=year,
        )
        details: dict[str, str] = {}

        body_text = page.inner_text("body")

        # Extract key-value pairs from definition lists or tables
        try:
            rows = page.query_selector_all("tr, dl dt, .field-label")
            for row in rows:
                try:
                    text = (row.inner_text() or "").strip()
                    if not text or len(text) > 200:
                        continue
                    # For table rows, grab sibling td
                    tag = row.evaluate("el => el.tagName.toLowerCase()")
                    if tag == "tr":
                        cells = row.query_selector_all("td, th")
                        if len(cells) >= 2:
                            key = (cells[0].inner_text() or "").strip().rstrip(":")
                            val = (cells[1].inner_text() or "").strip()
                            if key and val:
                                details[key] = val
                    elif tag == "dt":
                        # Try to get paired dd
                        val_el = row.evaluate_handle(
                            "el => el.nextElementSibling"
                        )
                        val = ""
                        try:
                            val = (val_el.as_element().inner_text() or "").strip()
                        except Exception:
                            pass
                        key = text.rstrip(":")
                        if key and val:
                            details[key] = val
                except Exception:
                    continue
        except Exception:
            logger.debug("Could not extract structured fields from page")

        # Map known field names to result fields
        body_lower = body_text.lower()
        for key, val in details.items():
            key_lower = key.lower()
            if "title" in key_lower and "status" in key_lower:
                result.title_status = val
            elif "lien" in key_lower:
                result.lien_status = val
            elif "make" in key_lower and not result.make:
                result.make = val
            elif "year" in key_lower and not result.model_year:
                result.model_year = val
            elif any(w in key_lower for w in ("vehicle", "description", "model")):
                result.vehicle_description = val

        # Fallback: scan body text for status keywords
        if not result.title_status:
            if "clear" in body_lower:
                result.title_status = "Clear"
            elif "salvage" in body_lower:
                result.title_status = "Salvage"
            elif "junk" in body_lower:
                result.title_status = "Junk"
            elif "rebuilt" in body_lower:
                result.title_status = "Rebuilt"

        if not result.lien_status:
            if "no lien" in body_lower or "lien: no" in body_lower:
                result.lien_status = "No lien"
            elif "lien" in body_lower:
                result.lien_status = "Lien reported"

        result.details = details

        logger.info(
            "NY DMV results — vin=%s, title=%s, lien=%s",
            vin,
            result.title_status,
            result.lien_status,
        )
        return result
