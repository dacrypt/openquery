"""Florida DHSMV vehicle title/registration check source.

Queries the Florida Department of Highway Safety and Motor Vehicles (DHSMV)
Motor Vehicle Check portal for title status, brand history, odometer reading,
and registration events.

Free public service — no login required. BotDetect image CAPTCHA present.

Flow:
1. Navigate to https://services.flhsmv.gov/mvcheckweb/
2. Fill #VehicleIdentificationNumber (VIN) or #TitleNumber (plate/title)
3. Solve BotDetect image CAPTCHA via LLM vision → OCR chain
4. Submit form via #continueButton
5. Wait for page load
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
            requires_captcha=True,
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
        """Full flow: launch browser, fill form, solve CAPTCHA, parse results."""
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

                # The form has two text fields: TitleNumber and VehicleIdentificationNumber.
                # No radio buttons — just fill the appropriate field.
                if search_type == "vin":
                    field = page.locator("#VehicleIdentificationNumber")
                else:
                    # plate search uses TitleNumber field (closest available match)
                    field = page.locator("#TitleNumber")

                field.wait_for(state="visible", timeout=15000)
                field.fill(value)
                logger.info("Filled %s field: %s", search_type, value)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Solve BotDetect image CAPTCHA — fill #CaptchaCode directly
                self._solve_captcha(page)

                if collector:
                    collector.screenshot(page, "captcha_solved")

                # Click submit (id="continueButton")
                submit_btn = page.locator("#continueButton")
                submit_btn.wait_for(state="visible", timeout=10000)
                submit_btn.click()
                logger.info("Clicked submit button")

                # Wait for page to finish loading after form submission
                page.wait_for_load_state("networkidle", timeout=20000)
                page.wait_for_timeout(1500)

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

    def _solve_captcha(self, page) -> None:
        """Solve BotDetect image CAPTCHA using vision chain, filling #CaptchaCode."""
        from openquery.core.captcha import ChainedSolver, LLMCaptchaSolver, OCRSolver

        # CAPTCHA image: .LBD_CaptchaImage
        captcha_img = page.query_selector(".LBD_CaptchaImage, #mvCheckCaptcha_CaptchaImage")
        if not captcha_img:
            logger.debug("No CAPTCHA image found — skipping CAPTCHA solve")
            return

        # Build solver chain: LLM vision first (most accurate for distorted text), then OCR
        solvers: list = []
        try:
            solvers.append(LLMCaptchaSolver(max_chars=6))
        except Exception:
            pass
        solvers.append(OCRSolver(max_chars=6))
        chain = ChainedSolver(solvers)

        # #CaptchaCode is the visible text input (not the hidden LBD_VCID_ field)
        captcha_input = page.locator("#CaptchaCode")

        for attempt in range(1, 4):
            try:
                image_bytes = captcha_img.screenshot()
                if not image_bytes or len(image_bytes) < 100:
                    logger.warning("CAPTCHA screenshot too small on attempt %d", attempt)
                    continue
                text = chain.solve(image_bytes)
                if text:
                    captcha_input.fill(text.strip().upper())
                    logger.info("CAPTCHA solved (attempt %d): %s", attempt, text)
                    return
            except Exception as e:
                logger.warning("CAPTCHA solve attempt %d failed: %s", attempt, e)

            # Refresh CAPTCHA image for next attempt
            refresh = page.query_selector(
                "#mvCheckCaptcha_ReloadIcon, a[onclick*='mvCheckCaptcha']"
            )
            if refresh:
                refresh.click()
                page.wait_for_timeout(800)

        logger.warning("All CAPTCHA solve attempts failed — submitting anyway")

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
                snippet = body_text[idx : idx + 80].strip()
                result.title_status = snippet
                details["title_status_raw"] = snippet
                break

        # Brand history — look for common brand keywords
        brands: list[str] = []
        brand_keywords = (
            "salvage",
            "rebuilt",
            "flood",
            "lemon",
            "theft",
            "junk",
            "dismantled",
            "non-repairable",
            "odometer rollback",
            "fire",
        )
        for kw in brand_keywords:
            if kw in body_lower:
                brands.append(kw.title())
        result.brand_history = brands

        # Odometer
        for phrase in ("odometer", "mileage"):
            idx = body_lower.find(phrase)
            if idx != -1:
                snippet = body_text[idx : idx + 60].strip()
                result.odometer = snippet
                details["odometer_raw"] = snippet
                break

        # Registration status
        for phrase in ("registration status", "registration:", "reg status"):
            idx = body_lower.find(phrase)
            if idx != -1:
                snippet = body_text[idx : idx + 80].strip()
                result.registration_status = snippet
                details["registration_raw"] = snippet
                break

        # Vehicle description — year/make/model typically near top.
        # Exclude modal headings (id contains "Modal") to avoid picking up "Warning".
        for selector in (
            ".panel-body h2",
            ".panel-body h3",
            "[class*='vehicle'] h2",
            "[class*='vehicle'] h3",
            "[class*='result'] h2",
            "[class*='result'] h3",
            "h2:not([id*='Modal'])",
            "h3:not([id*='Modal']):not(.modal-title)",
        ):
            try:
                el = page.query_selector(selector)
                if el:
                    text = (el.inner_text() or "").strip()
                    if text and text.lower() != "warning" and len(text) < 200:
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
