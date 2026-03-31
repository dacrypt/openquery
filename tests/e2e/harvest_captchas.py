"""Harvest real RUNT captchas for testing.

Downloads N captchas from the RUNT API using Playwright (needed for WAF cookies),
saves them as PNG files in tests/fixtures/captchas/ with the captcha ID as filename.

Usage:
    uv run python tests/e2e/harvest_captchas.py [--count 20]
"""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "captchas"
RUNT_PAGE = "https://www.runt.gov.co/consultaCiudadana/#/consultaVehiculo"
CAPTCHA_URL = "https://runtproapi.runt.gov.co/CYRConsultaVehiculoMS/captcha/libre-captcha/generar"


def harvest(count: int = 20) -> None:
    from playwright.sync_api import sync_playwright

    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(30000)

        print("Navigating to RUNT to acquire WAF cookies...")
        page.goto(RUNT_PAGE, wait_until="networkidle", timeout=30000)

        harvested = 0
        errors = 0

        for i in range(count):
            try:
                result = page.evaluate(f"""async () => {{
                    const r = await fetch('{CAPTCHA_URL}');
                    const data = await r.json();
                    return {{
                        id: data.id || data.idLibreCaptcha || '',
                        imagen: data.imagen || data.image || data.captcha || '',
                    }};
                }}""")

                captcha_id = result.get("id", "")
                image_data = result.get("imagen", "")

                if not captcha_id or not image_data:
                    print(f"  [{i+1}/{count}] SKIP — no id or image")
                    errors += 1
                    continue

                if "," in image_data:
                    image_data = image_data.split(",", 1)[1]

                image_bytes = base64.b64decode(image_data)

                if len(image_bytes) < 100:
                    print(f"  [{i+1}/{count}] SKIP — image too small ({len(image_bytes)}b)")
                    errors += 1
                    continue

                # Save PNG
                filepath = FIXTURES_DIR / f"{captcha_id}.png"
                filepath.write_bytes(image_bytes)

                # Also try to solve it
                from openquery.core.captcha import OCRSolver
                solver = OCRSolver(max_chars=5)
                try:
                    text = solver.solve(image_bytes)
                    status = f"OCR: '{text}'"
                except Exception as e:
                    text = ""
                    status = f"OCR FAIL: {e}"

                print(f"  [{i+1}/{count}] {captcha_id[:12]}... -> {status}")
                harvested += 1

                # Save metadata
                meta_path = FIXTURES_DIR / f"{captcha_id}.json"
                meta_path.write_text(json.dumps({
                    "id": captcha_id,
                    "ocr_result": text,
                    "ground_truth": "",  # Fill manually after visual inspection
                    "size_bytes": len(image_bytes),
                }, indent=2))

                # Small delay to be polite
                page.wait_for_timeout(500)

            except Exception as e:
                print(f"  [{i+1}/{count}] ERROR: {e}")
                errors += 1

        browser.close()

    print(f"\nDone: {harvested} captchas saved, {errors} errors")
    print(f"Location: {FIXTURES_DIR}")
    print("\nNext steps:")
    print("  1. Open the PNG files and write the correct text into each .json 'ground_truth' field")
    print("  2. Run: uv run pytest tests/e2e/test_ocr_accuracy.py -v")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Harvest RUNT captchas")
    parser.add_argument("--count", type=int, default=20, help="Number of captchas to download")
    args = parser.parse_args()
    harvest(args.count)
