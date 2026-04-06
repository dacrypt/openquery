"""Illinois SOS title/registration status source.

Queries the Illinois Secretary of State's vehicle registration/title status
portal via headless browser. No login or CAPTCHA required.

Flow:
1. Navigate to https://apps.ilsos.gov/regstatus/
2. Wait for the VIN input form to load
3. Fill in the VIN and submit
4. Wait for results page
5. Parse title status, registration status, lien info, fees, and vehicle description
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.us.il_sos import IlSosResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

IL_SOS_URL = "https://apps.ilsos.gov/regstatus/"


@register
class IlSosSource(BaseSource):
    """Query Illinois SOS for vehicle title and registration status."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="us.il_sos",
            display_name="Illinois SOS — Title/Registration Status",
            description="Illinois Secretary of State vehicle title and registration status — checks active/inactive status, lien info, and outstanding fees",  # noqa: E501
            country="US",
            url=IL_SOS_URL,
            supported_inputs=[DocumentType.VIN],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query Illinois SOS for title and registration status."""
        if input.document_type != DocumentType.VIN:
            raise SourceError("us.il_sos", f"Unsupported input type: {input.document_type}")

        vin = input.document_number.strip().upper()
        if not vin:
            raise SourceError("us.il_sos", "VIN is required")

        return self._query(vin, audit=input.audit)

    def _query(self, vin: str, audit: bool = False) -> IlSosResult:
        """Full flow: launch browser, fill form, parse results."""
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("us.il_sos", "vin", vin)

        with browser.page(IL_SOS_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                # Wait for the VIN input to appear — id="nbr", name="nbr"
                logger.info("Waiting for IL SOS form...")
                vin_input = page.locator("input#nbr, input[name='nbr']").first
                vin_input.wait_for(state="visible", timeout=15000)

                # Fill VIN
                vin_input.fill(vin)
                logger.info("Filled VIN: %s", vin)

                # Wait for JS to enable the submit button (it loads with disabled attr)
                submit_btn = page.locator("input[type='submit'][name='submit']").first
                page.wait_for_function(
                    "() => !document.querySelector(\"input[type='submit'][name='submit']\")?.disabled",  # noqa: E501
                    timeout=5000,
                )

                if collector:
                    collector.screenshot(page, "form_filled")

                submit_btn.click()
                logger.info("Clicked submit button")

                # Wait for results to appear
                page.wait_for_selector(
                    "table, [class*='result' i], [id*='result' i], "
                    "[class*='status' i], [id*='status' i], "
                    "h2, h3",
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
                raise SourceError("us.il_sos", f"Query failed: {e}") from e

    def _parse_results(self, page, vin: str) -> IlSosResult:
        """Parse the IL SOS results page."""
        result = IlSosResult(queried_at=datetime.now(), vin=vin)
        details: dict[str, str] = {}

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        # Try to extract label/value pairs from table rows first
        try:
            rows = page.query_selector_all("tr")
            for row in rows:
                cells = row.query_selector_all("td, th")
                if len(cells) >= 2:
                    label = (cells[0].inner_text() or "").strip().rstrip(":").lower()
                    value = (cells[1].inner_text() or "").strip()
                    if label and value:
                        details[label] = value
                        self._assign_field(result, label, value)
        except Exception:
            logger.debug("Table row parsing failed, falling back to text scan")

        # Fallback: scan body text for known patterns (only for fields not yet populated)
        needs_fallback = not any(
            [
                result.title_status,
                result.registration_status,
                result.lien_info,
                result.outstanding_fees,
            ]
        )
        if needs_fallback:
            for line in body_text.splitlines():
                line_lower = line.lower().strip()
                if (
                    not result.title_status
                    and "title" in line_lower
                    and (
                        "active" in line_lower or "inactive" in line_lower or "status" in line_lower
                    )
                ):
                    result.title_status = line.strip()
                elif (
                    not result.registration_status
                    and "registration" in line_lower
                    and (
                        "active" in line_lower or "inactive" in line_lower or "status" in line_lower
                    )
                ):
                    result.registration_status = line.strip()
                elif not result.lien_info and "lien" in line_lower:
                    result.lien_info = line.strip()
                elif not result.outstanding_fees and (
                    "fee" in line_lower or "outstanding" in line_lower
                ):
                    result.outstanding_fees = line.strip()

        # Try to capture vehicle description from known selectors
        if not result.vehicle_description:
            for selector in (
                "[class*='vehicle' i]",
                "[id*='vehicle' i]",
                "[class*='description' i]",
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

        # Check for error/not-found response
        if any(
            phrase in body_lower
            for phrase in ("not found", "no record", "invalid vin", "no results")
        ):
            if not result.title_status:
                result.title_status = "Not found"

        result.details = details

        logger.info(
            "IL SOS results — vin=%s, title=%s, registration=%s",
            vin,
            result.title_status,
            result.registration_status,
        )
        return result

    def _assign_field(self, result: IlSosResult, label: str, value: str) -> None:
        """Map a parsed label/value pair to the appropriate result field."""
        if "title" in label and "status" in label:
            result.title_status = value
        elif "registration" in label and "status" in label:
            result.registration_status = value
        elif "lien" in label:
            result.lien_info = value
        elif "fee" in label or "outstanding" in label:
            result.outstanding_fees = value
        elif "vehicle" in label or "year" in label or "make" in label or "model" in label:
            if result.vehicle_description:
                result.vehicle_description += f" {value}"
            else:
                result.vehicle_description = value
