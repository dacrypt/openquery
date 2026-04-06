"""End-to-end tests for RUNT source.

These tests hit the real RUNT API. They require:
- Network access
- Playwright + Chromium installed
- tesseract installed

Run: uv run pytest tests/e2e/test_runt_e2e.py -v -s -m integration
"""

from __future__ import annotations

import pytest

from openquery.exceptions import SourceError
from openquery.models.co.runt import RuntResult
from openquery.sources.base import DocumentType, QueryInput
from openquery.sources.co.runt import RuntSource

# Use VIN for testing since it's more reliable than plate
# (any valid Tesla VIN format should return data if registered)
TEST_VIN = "LRWYGCEK3TC512197"


@pytest.fixture
def runt():
    return RuntSource(timeout=30.0, headless=True)


@pytest.mark.integration
class TestRuntE2E:
    """End-to-end RUNT queries against the real API."""

    def test_query_by_vin(self, runt):
        """Query RUNT by VIN — most reliable query type."""
        try:
            result = runt.query(
                QueryInput(
                    document_type=DocumentType.VIN,
                    document_number=TEST_VIN,
                )
            )
            assert isinstance(result, RuntResult)
            print(f"\nVIN result: {result.marca} {result.linea} {result.modelo_ano}")
            print(f"  Estado: {result.estado}")
            print(f"  Placa: {result.placa}")
        except SourceError as e:
            # If VIN not yet registered (pre-delivery), this is expected
            if "no hay información" in str(e).lower():
                pytest.skip(f"VIN {TEST_VIN} not yet registered in RUNT")
            raise

    def test_query_invalid_plate_returns_or_errors(self, runt):
        """Querying a non-existent plate should raise or return empty."""
        try:
            result = runt.query(
                QueryInput(
                    document_type=DocumentType.PLATE,
                    document_number="ZZZ000",
                )
            )
            # If it returns, data should indicate not found
            print(f"\nInvalid plate result: estado='{result.estado}'")
        except SourceError as e:
            # Expected — "no hay información registrada"
            assert "no hay información" in str(e).lower() or "captcha" in str(e).lower()
            print(f"\nExpected error for invalid plate: {e}")


@pytest.mark.integration
class TestRuntCaptchaE2E:
    """Test the captcha generation and solving pipeline end-to-end."""

    def test_generate_captcha(self, runt):
        """Should generate a captcha from the real RUNT API."""
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=True, timeout=30.0)

        with browser.page(
            "https://www.runt.gov.co/consultaCiudadana/#/consultaVehiculo",
            wait_until="networkidle",
        ) as page:
            captcha_id, image_bytes = runt._generate_captcha(page)

            assert len(captcha_id) > 10, f"Captcha ID too short: {captcha_id}"
            assert len(image_bytes) > 100, f"Image too small: {len(image_bytes)} bytes"
            print(f"\nCaptcha ID: {captcha_id}")
            print(f"Image size: {len(image_bytes)} bytes")

    def test_generate_and_solve_captcha(self, runt):
        """Should generate AND solve a real captcha."""
        from openquery.core.browser import BrowserManager
        from openquery.core.captcha import OCRSolver

        browser = BrowserManager(headless=True, timeout=30.0)
        solver = OCRSolver(max_chars=5)

        with browser.page(
            "https://www.runt.gov.co/consultaCiudadana/#/consultaVehiculo",
            wait_until="networkidle",
        ) as page:
            captcha_id, image_bytes = runt._generate_captcha(page)
            result = solver.solve(image_bytes)

            assert result.isalnum(), f"Non-alphanumeric: '{result}'"
            assert 3 <= len(result) <= 5, f"Wrong length: '{result}'"
            print(f"\nCaptcha solved: '{result}'")

    def test_solve_multiple_captchas(self, runt):
        """Solve 5 captchas to verify consistency."""
        from openquery.core.browser import BrowserManager
        from openquery.core.captcha import OCRSolver

        browser = BrowserManager(headless=True, timeout=30.0)
        solver = OCRSolver(max_chars=5)

        results = []
        errors = 0

        with browser.page(
            "https://www.runt.gov.co/consultaCiudadana/#/consultaVehiculo",
            wait_until="networkidle",
        ) as page:
            for i in range(5):
                try:
                    _, image_bytes = runt._generate_captcha(page)
                    text = solver.solve(image_bytes)
                    results.append(text)
                except Exception as e:
                    errors += 1
                    results.append(f"ERROR: {e}")
                page.wait_for_timeout(300)

        print(f"\nSolved {len(results) - errors}/5 captchas:")
        for i, r in enumerate(results, 1):
            print(f"  {i}. {r}")

        assert errors <= 2, f"Too many failures: {errors}/5"
