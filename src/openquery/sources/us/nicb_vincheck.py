"""NICB VINCheck source — stolen/salvage vehicle check.

Queries the National Insurance Crime Bureau's VINCheck service via headless
browser.  The service checks whether a vehicle has been reported stolen (and
not recovered) or declared as a total loss (salvage).

Free public service — 5 lookups per 24 h per IP address.
Requires a reCAPTCHA v2 solver (OPENQUERY_CAPSOLVER_API_KEY or similar).

Flow:
1. Navigate to https://www.nicb.org/vincheck
2. Wait for the page JS to render the form
3. Intercept the /vincheck_ajax JSON response
4. Solve reCAPTCHA v2 via solver API
5. Inject token into window.vincheckRecaptchaResponse and set
   window.vincheckRecaptchaChallengePassed = true
6. Fill input[name='vin'], check agree_terms, click submit
7. Parse intercepted JSON: result.theft + result.totalloss
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.us.nicb_vincheck import NicbVincheckResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

NICB_URL = "https://www.nicb.org/vincheck"
NICB_SITEKEY = "6LcYETIUAAAAAKz6T9MxMEllN8yw0ffsErIbAGS-"


@register
class NicbVincheckSource(BaseSource):
    """Query NICB VINCheck for stolen/total-loss vehicle records."""

    def __init__(self, timeout: float = 60.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="us.nicb_vincheck",
            display_name="NICB VINCheck — Stolen/Salvage Check",
            description="National Insurance Crime Bureau VINCheck — checks if a vehicle was reported stolen or declared a total loss",  # noqa: E501
            country="US",
            url=NICB_URL,
            supported_inputs=[DocumentType.VIN],
            requires_captcha=True,
            requires_browser=True,
            rate_limit_rpm=5,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query NICB VINCheck for theft and total-loss records."""
        if input.document_type != DocumentType.VIN:
            raise SourceError("us.nicb_vincheck", f"Unsupported input type: {input.document_type}")

        vin = input.document_number.strip().upper()
        if not vin:
            raise SourceError("us.nicb_vincheck", "VIN is required")

        return self._query(vin, audit=input.audit)

    def _query(self, vin: str, audit: bool = False) -> NicbVincheckResult:
        """Full flow: launch browser, solve reCAPTCHA, intercept API, parse."""
        from openquery.core.browser import BrowserManager
        from openquery.core.captcha import build_recaptcha_solver

        solver = build_recaptcha_solver()
        if not solver:
            raise SourceError(
                "us.nicb_vincheck",
                "reCAPTCHA v2 solver required. Set OPENQUERY_CAPSOLVER_API_KEY "
                "or another provider API key.",
            )

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("us.nicb_vincheck", "vin", vin)

        api_data: dict = {}

        with browser.page(NICB_URL, wait_until="domcontentloaded") as page:
            try:
                if collector:
                    collector.attach(page)

                # Intercept the /vincheck_ajax JSON response
                def handle_response(response):
                    if "/vincheck_ajax" in response.url and response.status == 200:
                        try:
                            api_data.update(json.loads(response.text()))
                        except Exception:
                            pass

                page.on("response", handle_response)

                # Wait for the VIN form to render (JS-rendered)
                logger.info("Waiting for VINCheck form...")
                page.wait_for_selector(
                    ".nicb-vincheck-form-query input[name='vin']",
                    timeout=20000,
                )

                # Solve reCAPTCHA v2
                logger.info("Solving reCAPTCHA v2...")
                token = solver.solve_recaptcha_v2(NICB_SITEKEY, NICB_URL)
                logger.info("reCAPTCHA solved, injecting token...")

                # Inject token via the site's own callback mechanism
                page.evaluate(f"""() => {{
                    window.vincheckRecaptchaChallengePassed = true;
                    window.vincheckRecaptchaResponse = {json.dumps(token)};
                }}""")

                # Fill VIN input
                vin_input = page.locator(".nicb-vincheck-form-query input[name='vin']")
                vin_input.fill(vin)
                logger.info("Filled VIN: %s", vin)

                # Check terms checkbox
                terms = page.locator(".nicb-vincheck-form-query input[name='agree_terms']")
                if not terms.is_checked():
                    terms.check()
                    logger.info("Accepted terms checkbox")

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit the form
                submit_btn = page.locator(".nicb-vincheck-form-query button[type='submit']")
                submit_btn.click()
                logger.info("Clicked submit")

                # Wait for the API response (intercepted above) or results page
                page.wait_for_selector(
                    ".nicb-vincheck-form-result",
                    state="visible",
                    timeout=30000,
                )
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_results(vin, api_data, page)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("us.nicb_vincheck", f"Query failed: {e}") from e

    def _parse_results(self, vin: str, api_data: dict, page) -> NicbVincheckResult:
        """Parse /vincheck_ajax JSON response into NicbVincheckResult."""
        result = NicbVincheckResult(queried_at=datetime.now(), vin=vin)
        details: list[str] = []

        if api_data:
            api_result = api_data.get("result", {})
            has_theft = bool(api_result.get("theft", False))
            has_totalloss = bool(api_result.get("totalloss", False))

            result.theft_records_found = has_theft
            result.salvage_records_found = has_totalloss

            if has_theft:
                details.append("Theft record found")
            else:
                details.append("No theft records found")

            if has_totalloss:
                loss_items = api_result.get("totalloss_items", [])
                if loss_items:
                    dates = [item.get("date", "") for item in loss_items if item.get("date")]
                    causes = [item.get("cause", "") for item in loss_items if item.get("cause")]
                    detail = "Total loss record found"
                    if dates:
                        detail += f" (date: {dates[0]})"
                    if causes:
                        detail += f", cause: {causes[0]}"
                    details.append(detail)
                else:
                    details.append("Total loss record found")
            else:
                details.append("No total loss records found")

            result.status_message = (
                "Warning: theft or total loss record found"
                if (has_theft or has_totalloss)
                else "No records found"
            )
        else:
            # Fallback: parse page body text if API data not intercepted
            body_text = page.inner_text("body").lower()
            if "has not been identified" in body_text:
                result.theft_records_found = False
                result.salvage_records_found = False
                details.append("No records found (page text)")
            elif "has been identified" in body_text:
                if "theft" in body_text:
                    result.theft_records_found = True
                    details.append("Theft record found (page text)")
                if "total loss" in body_text or "salvage" in body_text:
                    result.salvage_records_found = True
                    details.append("Total loss record found (page text)")
            result.status_message = "Parsed from page text (API not intercepted)"

        result.details = details

        logger.info(
            "VINCheck results — vin=%s, theft=%s, totalloss=%s",
            vin,
            result.theft_records_found,
            result.salvage_records_found,
        )
        return result
