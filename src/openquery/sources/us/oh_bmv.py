"""Ohio BMV title search source.

Queries the Ohio Bureau of Motor Vehicles online title search portal via
headless browser. No login required.

Flow:
1. Navigate to https://bmvonline.dps.ohio.gov/bmvonline/titles/titlesearch
2. Wait for the search form to load
3. Fill the VIN (or title number) input field
4. Submit the form
5. Wait for results
6. Parse ownership, lien status, title status, and vehicle description
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.us.oh_bmv import OhBmvResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

OH_BMV_URL = "https://bmvonline.dps.ohio.gov/bmvonline/titles/titlesearch"


@register
class OhBmvSource(BaseSource):
    """Query Ohio BMV title search for ownership and lien status."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="us.oh_bmv",
            display_name="Ohio BMV — Title Search",
            description=(
                "Ohio Bureau of Motor Vehicles title search — ownership verification, "
                "lien status, and title history"
            ),
            country="US",
            url=OH_BMV_URL,
            supported_inputs=[DocumentType.VIN],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query Ohio BMV title search."""
        if input.document_type != DocumentType.VIN:
            raise SourceError("us.oh_bmv", f"Unsupported input type: {input.document_type}")

        vin = input.document_number.strip().upper()
        if not vin:
            raise SourceError("us.oh_bmv", "VIN is required")

        return self._query(vin, audit=input.audit)

    def _query(self, vin: str, audit: bool = False) -> OhBmvResult:
        """Full flow: launch browser, fill form, parse results."""
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("us.oh_bmv", "vin", vin)

        with browser.page(OH_BMV_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                # Wait for the VIN input to appear
                logger.info("Waiting for Ohio BMV title search form...")
                vin_input = page.locator(
                    "input[name*='vin'], input[id*='vin'], "
                    "input[placeholder*='VIN'], input[placeholder*='vin'], "
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
                    "button:has-text('Submit'), "
                    "button:has-text('Find')"
                ).first
                submit_btn.click()
                logger.info("Clicked submit button")

                # Wait for results to appear
                page.wait_for_selector(
                    "table, [class*='result'], [class*='Result'], "
                    "[id*='result'], [class*='title'], h2, h3",
                    timeout=20000,
                )
                page.wait_for_timeout(1500)

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
                raise SourceError("us.oh_bmv", f"Query failed: {e}") from e

    def _parse_results(self, page, vin: str) -> OhBmvResult:
        """Parse the Ohio BMV title search results page."""
        result = OhBmvResult(queried_at=datetime.now(), vin=vin)
        details: dict[str, str] = {}

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        # Try to extract table rows (key-value pairs)
        try:
            rows = page.query_selector_all("table tr, dl dt, dl dd, .field-label, .field-value")
            cells = [r.inner_text().strip() for r in rows if r.inner_text().strip()]
            # Pair adjacent cells as key: value
            for i in range(0, len(cells) - 1, 2):
                key = cells[i].rstrip(":").strip()
                value = cells[i + 1].strip()
                if key and value:
                    details[key] = value
        except Exception:
            logger.debug("Table parsing failed, falling back to text extraction")

        # Extract known fields from details dict or body text
        for key, val in details.items():
            key_lower = key.lower()
            if "title" in key_lower and "status" in key_lower:
                result.title_status = val
            elif "lien" in key_lower:
                result.lien_status = val
            elif "vehicle" in key_lower and any(
                w in key_lower for w in ("desc", "make", "model", "year")
            ):
                if result.vehicle_description:
                    result.vehicle_description += f" {val}"
                else:
                    result.vehicle_description = val
            elif "owner" in key_lower:
                result.owner_verification = val
            elif "title" in key_lower and "number" in key_lower:
                result.title_number = val

        # Fallback: scan body text for lien status keywords
        if not result.lien_status:
            no_lien_phrases = ("no lien", "no liens", "lien free", "lien: no")
            lien_phrases = ("lien holder", "lienholder", "lien: yes", "lien recorded")
            if any(phrase in body_lower for phrase in no_lien_phrases):
                result.lien_status = "No Lien"
            elif any(phrase in body_lower for phrase in lien_phrases):
                result.lien_status = "Lien Recorded"

        # Fallback: scan body text for title status keywords
        if not result.title_status:
            for phrase in ("clean title", "salvage", "rebuilt", "junk", "flood", "active"):
                if phrase in body_lower:
                    result.title_status = phrase.title()
                    break

        result.details = details

        logger.info(
            "Ohio BMV results — vin=%s, title_status=%s, lien_status=%s",
            vin,
            result.title_status,
            result.lien_status,
        )
        return result
