"""Benchmark: tesseract OCR vs TrOCR on real RUNT captchas.

Compares accuracy and speed of both solvers against annotated ground truth.

Usage:
    uv run python tests/e2e/bench_solvers.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "captchas"


def load_samples() -> list[tuple[str, bytes, str]]:
    samples = []
    for json_path in sorted(FIXTURES_DIR.glob("*.json")):
        meta = json.loads(json_path.read_text())
        gt = meta.get("ground_truth", "")
        if not gt:
            continue
        png_path = json_path.with_suffix(".png")
        if not png_path.exists():
            continue
        samples.append((meta["id"][:12], png_path.read_bytes(), gt))
    return samples


def bench_solver(solver, samples, name):
    correct = 0
    errors = 0
    total_time = 0.0
    results = []

    for cid, image_bytes, gt in samples:
        start = time.monotonic()
        try:
            result = solver.solve(image_bytes)
            elapsed = time.monotonic() - start
            match = result == gt
            if match:
                correct += 1
            results.append((cid, gt, result, match, elapsed))
        except Exception as e:
            elapsed = time.monotonic() - start
            errors += 1
            results.append((cid, gt, f"ERR:{e}", False, elapsed))
        total_time += elapsed

    total = len(samples)
    accuracy = correct / total if total else 0

    # Case-insensitive accuracy
    ci_correct = sum(
        1
        for _, gt, result, _, _ in results
        if not result.startswith("ERR:") and result.lower() == gt.lower()
    )
    ci_accuracy = ci_correct / total if total else 0

    print(f"\n{'=' * 60}")
    print(f" {name}")
    print(f"{'=' * 60}")
    print(f"{'ID':<14} {'Truth':<8} {'Result':<8} {'Exact':<6} {'CI':<6} {'Time'}")
    print("-" * 60)
    for cid, gt, result, match, elapsed in results:
        exact = "OK" if match else "FAIL"
        ci = "OK" if not result.startswith("ERR:") and result.lower() == gt.lower() else "FAIL"
        print(f"{cid:<14} {gt:<8} {result:<8} {exact:<6} {ci:<6} {elapsed * 1000:.0f}ms")

    print(f"\nExact accuracy:    {correct}/{total} = {accuracy:.0%}")
    print(f"CI accuracy:       {ci_correct}/{total} = {ci_accuracy:.0%}")
    print(f"Errors: {errors}")
    print(f"Total time: {total_time:.1f}s")
    print(f"Avg per captcha: {total_time / total * 1000:.0f}ms")

    return accuracy, ci_accuracy


def main():
    samples = load_samples()
    print(f"Loaded {len(samples)} annotated captcha samples\n")

    # Tesseract
    from openquery.core.captcha import OCRSolver

    tesseract = OCRSolver(max_chars=5)
    acc_tess, ci_tess = bench_solver(tesseract, samples, "Tesseract (pytesseract)")

    # TrOCR
    from openquery.core.captcha import TrOCRSolver

    trocr = TrOCRSolver(max_chars=5)
    acc_trocr, ci_trocr = bench_solver(trocr, samples, "TrOCR (microsoft/trocr-small-printed)")

    # Summary
    print(f"\n{'=' * 60}")
    print(" SUMMARY")
    print(f"{'=' * 60}")
    print(f"{'Solver':<20} {'Exact':<12} {'Case-insensitive'}")
    print("-" * 48)
    print(f"{'Tesseract':<20} {acc_tess:<12.0%} {ci_tess:.0%}")
    print(f"{'TrOCR':<20} {acc_trocr:<12.0%} {ci_trocr:.0%}")


if __name__ == "__main__":
    main()
