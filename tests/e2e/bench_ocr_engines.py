#!/usr/bin/env python3
"""Benchmark multiple OCR engines against real RUNT captchas.

Compares: tesseract (current), paddleocr, doctr, easyocr
Measures: exact accuracy, case-insensitive accuracy, per-char accuracy, speed

Run:
  uv run python tests/e2e/bench_ocr_engines.py

Install engines to test:
  pip install paddlepaddle paddleocr    # PaddleOCR
  pip install "python-doctr[torch]"     # docTR
  pip install easyocr                   # EasyOCR
"""

from __future__ import annotations

import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "captchas"


def load_samples() -> list[dict]:
    samples = []
    for jp in sorted(FIXTURES_DIR.glob("*.json")):
        meta = json.loads(jp.read_text())
        gt = meta.get("ground_truth", "")
        if not gt:
            continue
        png = jp.with_suffix(".png")
        if not png.exists():
            continue
        meta["image_bytes"] = png.read_bytes()
        meta["image_path"] = str(png)
        samples.append(meta)
    return samples


# ---------------------------------------------------------------------------
# Engine wrappers
# ---------------------------------------------------------------------------

def solve_tesseract(image_bytes: bytes) -> str:
    """Current OCRSolver approach."""
    from openquery.core.captcha import OCRSolver
    solver = OCRSolver(max_chars=5)
    return solver.solve(image_bytes)


def solve_paddleocr(image_path: str) -> str:
    """PaddleOCR PP-OCRv5."""
    from paddleocr import PaddleOCR
    if not hasattr(solve_paddleocr, "_ocr"):
        solve_paddleocr._ocr = PaddleOCR(
            lang="en",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
    results = solve_paddleocr._ocr.predict(image_path)
    texts = []
    for r in results:
        if hasattr(r, "rec_texts"):
            texts.extend(r.rec_texts)
        elif isinstance(r, dict) and "rec_texts" in r:
            texts.extend(r["rec_texts"])
    text = "".join(texts)
    return re.sub(r"[^a-zA-Z0-9]", "", text)[:5]


def solve_doctr(image_path: str) -> str:
    """docTR with ViTSTR recognition."""
    from doctr.io import DocumentFile
    from doctr.models import ocr_predictor
    if not hasattr(solve_doctr, "_predictor"):
        solve_doctr._predictor = ocr_predictor(
            det_arch="db_mobilenet_v3_large",
            reco_arch="vitstr_small",
            pretrained=True,
        )
    doc = DocumentFile.from_images(image_path)
    result = solve_doctr._predictor(doc)
    texts = []
    for page in result.pages:
        for block in page.blocks:
            for line in block.lines:
                for word in line.words:
                    texts.append(word.value)
    text = "".join(texts)
    return re.sub(r"[^a-zA-Z0-9]", "", text)[:5]


def solve_easyocr(image_path: str) -> str:
    """EasyOCR."""
    import easyocr
    if not hasattr(solve_easyocr, "_reader"):
        solve_easyocr._reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    results = solve_easyocr._reader.readtext(image_path, detail=0)
    text = "".join(results)
    return re.sub(r"[^a-zA-Z0-9]", "", text)[:5]


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------

ENGINES = {
    "tesseract": lambda s: solve_tesseract(s["image_bytes"]),
    "paddleocr": lambda s: solve_paddleocr(s["image_path"]),
    "doctr": lambda s: solve_doctr(s["image_path"]),
    "easyocr": lambda s: solve_easyocr(s["image_path"]),
}


def check_available(name: str) -> bool:
    try:
        if name == "tesseract":
            import pytesseract  # noqa: F401
            return True
        elif name == "paddleocr":
            from paddleocr import PaddleOCR  # noqa: F401
            return True
        elif name == "doctr":
            from doctr.models import ocr_predictor  # noqa: F401
            return True
        elif name == "easyocr":
            import easyocr  # noqa: F401
            return True
    except ImportError:
        return False
    return False


def char_accuracy(result: str, truth: str) -> float:
    correct = sum(1 for a, b in zip(result, truth) if a == b)
    total = max(len(truth), len(result))
    return correct / total if total > 0 else 0


def run_benchmark():
    samples = load_samples()
    if not samples:
        print("No annotated captcha fixtures found in", FIXTURES_DIR)
        sys.exit(1)

    print(f"Loaded {len(samples)} captcha samples\n")

    # Detect available engines
    available = {name: fn for name, fn in ENGINES.items() if check_available(name)}
    unavailable = [name for name in ENGINES if name not in available]

    if unavailable:
        print(f"Unavailable engines (not installed): {', '.join(unavailable)}")
        print("Install with:")
        if "paddleocr" in unavailable:
            print("  pip install paddlepaddle paddleocr")
        if "doctr" in unavailable:
            print('  pip install "python-doctr[torch]"')
        if "easyocr" in unavailable:
            print("  pip install easyocr")
        print()

    if not available:
        print("No OCR engines available!")
        sys.exit(1)

    # Run each engine
    results = {}  # engine -> list of (id, truth, result, time_ms)

    for engine_name, solve_fn in available.items():
        print(f"Running {engine_name}...")
        engine_results = []

        for sample in samples:
            truth = sample["ground_truth"]
            start = time.monotonic()
            try:
                result = solve_fn(sample)
            except Exception as e:
                result = f"ERR:{e}"
            elapsed = (time.monotonic() - start) * 1000
            engine_results.append((sample["id"][:12], truth, result, elapsed))

        results[engine_name] = engine_results
        print(f"  Done ({len(engine_results)} samples)")

    # Print detailed comparison table
    print("\n" + "=" * 90)
    print("DETAILED RESULTS")
    print("=" * 90)

    header = f"{'ID':<14} {'Truth':<8}"
    for name in available:
        header += f" {name:<14}"
    print(header)
    print("-" * (14 + 8 + 14 * len(available)))

    for i, sample in enumerate(samples):
        row = f"{sample['id'][:12]:<14} {sample['ground_truth']:<8}"
        for name in available:
            _, truth, result, ms = results[name][i]
            mark = "OK" if result == truth else "FAIL"
            row += f" {result:<8}{mark:<6}"
        print(row)

    # Summary stats
    print("\n" + "=" * 90)
    print("SUMMARY")
    print("=" * 90)

    summary_header = f"{'Metric':<25}"
    for name in available:
        summary_header += f" {name:<14}"
    print(summary_header)
    print("-" * (25 + 14 * len(available)))

    for metric_name, metric_fn in [
        ("Exact accuracy", lambda r, t: r == t),
        ("Case-insensitive acc.", lambda r, t: r.lower() == t.lower()),
    ]:
        row = f"{metric_name:<25}"
        for name in available:
            correct = sum(1 for _, t, r, _ in results[name] if metric_fn(r, t))
            total = len(results[name])
            row += f" {correct}/{total} ({correct/total:.0%})    "
        print(row)

    # Character accuracy
    row = f"{'Character accuracy':<25}"
    for name in available:
        total_chars = 0
        correct_chars = 0
        for _, truth, result, _ in results[name]:
            for a, b in zip(result, truth):
                total_chars += 1
                if a == b:
                    correct_chars += 1
            total_chars += abs(len(result) - len(truth))
        acc = correct_chars / total_chars if total_chars > 0 else 0
        row += f" {correct_chars}/{total_chars} ({acc:.0%})    "
    print(row)

    # Average speed
    row = f"{'Avg speed (ms)':<25}"
    for name in available:
        avg = sum(ms for _, _, _, ms in results[name]) / len(results[name])
        row += f" {avg:<14.0f}"
    print(row)

    # P95 speed
    row = f"{'P95 speed (ms)':<25}"
    for name in available:
        times = sorted(ms for _, _, _, ms in results[name])
        p95 = times[int(len(times) * 0.95)]
        row += f" {p95:<14.0f}"
    print(row)

    # Confusion analysis per engine
    print("\n" + "=" * 90)
    print("CONFUSIONS PER ENGINE")
    print("=" * 90)

    for name in available:
        confusions = Counter()
        for _, truth, result, _ in results[name]:
            for a, b in zip(truth, result):
                if a != b:
                    confusions[(a, b)] += 1

        if confusions:
            print(f"\n{name}:")
            for (expected, got), count in confusions.most_common(10):
                print(f"  {expected!r} → {got!r}  ({count}x)")
        else:
            print(f"\n{name}: NO confusions (100% accurate)")

    # Complementarity analysis — which engines fix each other's errors?
    if len(available) >= 2:
        print("\n" + "=" * 90)
        print("COMPLEMENTARITY — Could combining engines help?")
        print("=" * 90)

        engine_names = list(available.keys())
        for i, name_a in enumerate(engine_names):
            for name_b in engine_names[i + 1:]:
                a_wrong_b_right = 0
                b_wrong_a_right = 0
                both_wrong = 0
                both_right = 0

                for j in range(len(samples)):
                    _, truth_a, result_a, _ = results[name_a][j]
                    _, truth_b, result_b, _ = results[name_b][j]

                    a_ok = result_a == truth_a
                    b_ok = result_b == truth_b

                    if a_ok and b_ok:
                        both_right += 1
                    elif a_ok and not b_ok:
                        b_wrong_a_right += 1
                    elif not a_ok and b_ok:
                        a_wrong_b_right += 1
                    else:
                        both_wrong += 1

                combined = both_right + a_wrong_b_right + b_wrong_a_right
                total = len(samples)
                print(f"\n{name_a} + {name_b}:")
                print(f"  Both right:           {both_right}/{total}")
                print(f"  {name_a} right, {name_b} wrong: {b_wrong_a_right}/{total}")
                print(f"  {name_b} right, {name_a} wrong: {a_wrong_b_right}/{total}")
                print(f"  Both wrong:           {both_wrong}/{total}")
                print(f"  Combined potential:    {combined}/{total} ({combined/total:.0%})")


if __name__ == "__main__":
    run_benchmark()
