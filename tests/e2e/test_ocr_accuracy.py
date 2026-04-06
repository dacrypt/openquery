"""OCR accuracy test against real RUNT captchas.

Uses harvested captcha images with manually annotated ground truth.
Measures character-level and word-level accuracy of the OCR pipeline.

Run: uv run pytest tests/e2e/test_ocr_accuracy.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openquery.core.captcha import OCRSolver

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "captchas"


def load_captcha_samples() -> list[tuple[str, bytes, str, str]]:
    """Load all captcha samples with ground truth.

    Returns list of (captcha_id, image_bytes, ground_truth, ocr_result_from_harvest).
    """
    samples = []
    for json_path in sorted(FIXTURES_DIR.glob("*.json")):
        meta = json.loads(json_path.read_text())
        gt = meta.get("ground_truth", "")
        if not gt:
            continue
        png_path = json_path.with_suffix(".png")
        if not png_path.exists():
            continue
        samples.append(
            (
                meta["id"],
                png_path.read_bytes(),
                gt,
                meta.get("ocr_result", ""),
            )
        )
    return samples


SAMPLES = load_captcha_samples()


@pytest.mark.skipif(len(SAMPLES) == 0, reason="No annotated captcha fixtures found")
class TestOCRAccuracy:
    """Test OCR accuracy against real RUNT captchas."""

    @pytest.fixture
    def solver(self):
        return OCRSolver(max_chars=5)

    @pytest.mark.parametrize(
        "captcha_id,image_bytes,ground_truth,_",
        SAMPLES,
        ids=[s[0][:12] for s in SAMPLES],
    )
    def test_ocr_produces_output(self, solver, captcha_id, image_bytes, ground_truth, _):
        """OCR should produce 3-5 alphanumeric characters for every real captcha."""
        result = solver.solve(image_bytes)
        assert result.isalnum(), f"Non-alphanumeric result: '{result}'"
        assert 3 <= len(result) <= 5, f"Wrong length: '{result}' ({len(result)} chars)"

    def test_word_accuracy_above_threshold(self, solver):
        """At least 60% of captchas should be solved exactly correct."""
        correct = 0
        total = len(SAMPLES)
        results = []

        for captcha_id, image_bytes, ground_truth, _ in SAMPLES:
            try:
                result = solver.solve(image_bytes)
                match = result == ground_truth
                if match:
                    correct += 1
                results.append((captcha_id[:12], ground_truth, result, match))
            except Exception as e:
                results.append((captcha_id[:12], ground_truth, f"ERROR: {e}", False))

        accuracy = correct / total if total > 0 else 0

        # Print detailed results
        print(f"\n{'ID':<14} {'Truth':<8} {'OCR':<8} {'Match'}")
        print("-" * 42)
        for cid, truth, ocr, match in results:
            mark = "OK" if match else "FAIL"
            print(f"{cid:<14} {truth:<8} {ocr:<8} {mark}")
        print(f"\nWord accuracy: {correct}/{total} = {accuracy:.0%}")

        assert accuracy >= 0.60, (
            f"Word accuracy {accuracy:.0%} is below 60% threshold. {correct}/{total} correct."
        )

    def test_character_accuracy_above_threshold(self, solver):
        """At least 85% of individual characters should be correct."""
        total_chars = 0
        correct_chars = 0

        for _, image_bytes, ground_truth, _ in SAMPLES:
            try:
                result = solver.solve(image_bytes)
                # Compare character by character (up to min length)
                for i in range(min(len(result), len(ground_truth))):
                    total_chars += 1
                    if result[i] == ground_truth[i]:
                        correct_chars += 1
                # Count missing/extra chars as errors
                total_chars += abs(len(result) - len(ground_truth))
            except Exception:
                total_chars += len(ground_truth)

        accuracy = correct_chars / total_chars if total_chars > 0 else 0
        print(f"\nCharacter accuracy: {correct_chars}/{total_chars} = {accuracy:.0%}")

        assert accuracy >= 0.85, (
            f"Character accuracy {accuracy:.0%} is below 85% threshold. "
            f"{correct_chars}/{total_chars} correct."
        )

    def test_retry_success_rate(self, solver):
        """With 3 retries, success probability should be very high.

        If single-attempt accuracy is p, then 3-retry success is 1-(1-p)^3.
        With p=0.80, that's 99.2%.
        This test verifies the math holds with our actual accuracy.
        """
        correct = sum(
            1
            for _, image_bytes, ground_truth, _ in SAMPLES
            if solver.solve(image_bytes) == ground_truth
        )
        p = correct / len(SAMPLES)
        retry_success = 1 - (1 - p) ** 3

        print(f"\nSingle attempt: {p:.0%}")
        print(f"3-retry success probability: {retry_success:.1%}")

        assert retry_success >= 0.95, (
            f"3-retry success rate {retry_success:.1%} is below 95% threshold"
        )
