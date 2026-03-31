"""Diagnostic tests to identify weaknesses in the captcha solving system.

These tests are designed to surface specific failure modes, confusion patterns,
preprocessing gaps, and architectural limitations — NOT to pass/fail in CI,
but to generate actionable improvement data.

Run: uv run pytest tests/test_captcha_diagnostics.py -v -s
"""

from __future__ import annotations

import io
import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

import pytest

from openquery.core.captcha import OCRSolver

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "captchas"


def load_samples() -> list[dict]:
    """Load all annotated captcha samples."""
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
        samples.append(meta)
    return samples


SAMPLES = load_samples()
SOLVER = OCRSolver(max_chars=5)


# ---------------------------------------------------------------------------
# 1. Character-level confusion matrix
# ---------------------------------------------------------------------------

@pytest.mark.skipif(len(SAMPLES) == 0, reason="No captcha fixtures")
class TestConfusionMatrix:
    """Build a confusion matrix to identify which character pairs the OCR confuses."""

    def test_confusion_pairs(self):
        """Identify the most common character confusions (expected→got)."""
        confusions: Counter = Counter()
        correct_by_char: Counter = Counter()
        total_by_char: Counter = Counter()

        for sample in SAMPLES:
            result = SOLVER.solve(sample["image_bytes"])
            truth = sample["ground_truth"]

            for i in range(min(len(result), len(truth))):
                total_by_char[truth[i]] += 1
                if result[i] == truth[i]:
                    correct_by_char[truth[i]] += 1
                else:
                    confusions[(truth[i], result[i])] += 1

        print("\n" + "=" * 60)
        print("CONFUSION MATRIX — Most common OCR errors")
        print("=" * 60)
        print(f"{'Expected':<10} {'Got':<10} {'Count':<8} {'Type'}")
        print("-" * 45)
        for (expected, got), count in confusions.most_common(20):
            confusion_type = _classify_confusion(expected, got)
            print(f"{expected!r:<10} {got!r:<10} {count:<8} {confusion_type}")

        print(f"\nTotal confusions: {sum(confusions.values())}")
        print(f"Unique confusion pairs: {len(confusions)}")

        # Per-character accuracy
        print("\n" + "=" * 60)
        print("PER-CHARACTER ACCURACY")
        print("=" * 60)
        print(f"{'Char':<6} {'Correct':<10} {'Total':<8} {'Accuracy'}")
        print("-" * 35)
        for char in sorted(total_by_char.keys()):
            total = total_by_char[char]
            correct = correct_by_char.get(char, 0)
            acc = correct / total if total > 0 else 0
            marker = " <<<" if acc < 0.8 else ""
            print(f"{char!r:<6} {correct:<10} {total:<8} {acc:.0%}{marker}")

        # This test always passes — it's diagnostic
        assert True


def _classify_confusion(expected: str, got: str) -> str:
    """Classify the type of character confusion."""
    similar_pairs = {
        frozenset({"5", "S"}): "digit-letter",
        frozenset({"8", "B"}): "digit-letter",
        frozenset({"0", "O"}): "digit-letter",
        frozenset({"0", "D"}): "digit-letter",
        frozenset({"1", "I"}): "digit-letter",
        frozenset({"1", "l"}): "digit-letter",
        frozenset({"2", "Z"}): "digit-letter",
        frozenset({"6", "G"}): "digit-letter",
        frozenset({"T", "I"}): "similar-shape",
        frozenset({"c", "e"}): "similar-shape",
        frozenset({"r", "n"}): "similar-shape",
        frozenset({"m", "n"}): "similar-shape",
        frozenset({"u", "v"}): "similar-shape",
        frozenset({"f", "t"}): "similar-shape",
        frozenset({"d", "a"}): "similar-shape",
        frozenset({"g", "q"}): "similar-shape",
        frozenset({"h", "b"}): "similar-shape",
    }
    pair = frozenset({expected, got})
    if pair in similar_pairs:
        return similar_pairs[pair]
    if expected.lower() == got.lower():
        return "case-error"
    if expected.isdigit() != got.isdigit():
        return "digit-letter"
    return "unknown"


# ---------------------------------------------------------------------------
# 2. Pipeline comparison — which preprocessing variant wins?
# ---------------------------------------------------------------------------

@pytest.mark.skipif(len(SAMPLES) == 0, reason="No captcha fixtures")
class TestPipelineComparison:
    """Compare individual preprocessing pipelines to find which is best."""

    def test_pipeline_accuracy_breakdown(self):
        """Show accuracy of each preprocessing pipeline independently."""
        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            pytest.skip("pytesseract/Pillow not available")

        ocr_config = (
            "--psm 8 -c tessedit_char_whitelist="
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        )

        pipeline_stats = defaultdict(lambda: {"correct": 0, "total": 0, "times": []})

        for sample in SAMPLES:
            truth = sample["ground_truth"]
            img = Image.open(io.BytesIO(sample["image_bytes"]))

            for i, preprocessed in enumerate(OCRSolver._preprocess_variants(img)):
                start = time.monotonic()
                text = pytesseract.image_to_string(preprocessed, config=ocr_config).strip()
                text = re.sub(r"[^a-zA-Z0-9]", "", text)[:5]
                elapsed = (time.monotonic() - start) * 1000

                pipeline_stats[f"pipeline_{i+1}"]["total"] += 1
                pipeline_stats[f"pipeline_{i+1}"]["times"].append(elapsed)
                if text == truth:
                    pipeline_stats[f"pipeline_{i+1}"]["correct"] += 1

        print("\n" + "=" * 60)
        print("PIPELINE ACCURACY BREAKDOWN")
        print("=" * 60)
        print(f"{'Pipeline':<15} {'Correct':<10} {'Total':<8} {'Accuracy':<10} {'Avg ms'}")
        print("-" * 55)
        for name, stats in sorted(pipeline_stats.items()):
            acc = stats["correct"] / stats["total"] if stats["total"] > 0 else 0
            avg_ms = sum(stats["times"]) / len(stats["times"]) if stats["times"] else 0
            print(f"{name:<15} {stats['correct']:<10} {stats['total']:<8} "
                  f"{acc:<10.0%} {avg_ms:.1f}")

        # Determine which pipelines are underperforming
        best_acc = max(
            s["correct"] / s["total"] for s in pipeline_stats.values() if s["total"] > 0
        )
        for name, stats in pipeline_stats.items():
            acc = stats["correct"] / stats["total"] if stats["total"] > 0 else 0
            if acc < best_acc * 0.7:
                print(f"\nWARNING: {name} accuracy ({acc:.0%}) is <70% of best ({best_acc:.0%})")

        assert True


# ---------------------------------------------------------------------------
# 3. Confidence calibration — is confidence a good predictor of correctness?
# ---------------------------------------------------------------------------

@pytest.mark.skipif(len(SAMPLES) == 0, reason="No captcha fixtures")
class TestConfidenceCalibration:
    """Test whether OCR confidence scores predict actual correctness."""

    def test_confidence_vs_accuracy(self):
        """Higher confidence should correlate with better accuracy."""
        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            pytest.skip("pytesseract/Pillow not available")

        ocr_config = (
            "--psm 8 -c tessedit_char_whitelist="
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        )

        results = []  # (confidence, is_correct, text, truth)

        for sample in SAMPLES:
            truth = sample["ground_truth"]
            img = Image.open(io.BytesIO(sample["image_bytes"]))

            for preprocessed in OCRSolver._preprocess_variants(img):
                text = pytesseract.image_to_string(preprocessed, config=ocr_config).strip()
                text = re.sub(r"[^a-zA-Z0-9]", "", text)[:5]

                try:
                    data = pytesseract.image_to_data(
                        preprocessed, config=ocr_config, output_type=pytesseract.Output.DICT,
                    )
                    confidences = [int(c) for c in data["conf"] if int(c) > 0]
                    avg_conf = sum(confidences) / len(confidences) if confidences else 0
                except Exception:
                    avg_conf = 0

                results.append((avg_conf, text == truth, text, truth))

        # Bin by confidence ranges
        bins = [(0, 30), (30, 50), (50, 70), (70, 85), (85, 100)]

        print("\n" + "=" * 60)
        print("CONFIDENCE CALIBRATION")
        print("=" * 60)
        print(f"{'Confidence':<15} {'Correct':<10} {'Total':<8} {'Accuracy'}")
        print("-" * 45)

        for low, high in bins:
            in_bin = [(c, ok) for c, ok, _, _ in results if low <= c < high]
            total = len(in_bin)
            correct = sum(1 for _, ok in in_bin if ok)
            acc = correct / total if total > 0 else 0
            print(f"{low:>3}-{high:<3}%        {correct:<10} {total:<8} {acc:.0%}")

        # Check if high confidence is actually reliable
        high_conf = [(c, ok) for c, ok, _, _ in results if c >= 70]
        low_conf = [(c, ok) for c, ok, _, _ in results if c < 50]

        if high_conf and low_conf:
            high_acc = sum(1 for _, ok in high_conf if ok) / len(high_conf)
            low_acc = sum(1 for _, ok in low_conf if ok) / len(low_conf)

            if high_acc <= low_acc:
                print("\nWARNING: High confidence is NOT more accurate than low confidence!")
                print("The confidence-based selection strategy may be ineffective.")
            else:
                print(f"\nConfidence discrimination: high={high_acc:.0%} vs low={low_acc:.0%}")

        assert True


# ---------------------------------------------------------------------------
# 4. Case sensitivity analysis
# ---------------------------------------------------------------------------

@pytest.mark.skipif(len(SAMPLES) == 0, reason="No captcha fixtures")
class TestCaseSensitivity:
    """Analyze how much accuracy improves if we ignore case."""

    def test_case_insensitive_vs_sensitive(self):
        """Compare case-sensitive vs case-insensitive accuracy."""
        exact_correct = 0
        ci_correct = 0
        case_only_errors = 0  # Wrong only due to case

        details = []

        for sample in SAMPLES:
            result = SOLVER.solve(sample["image_bytes"])
            truth = sample["ground_truth"]

            exact_match = result == truth
            ci_match = result.lower() == truth.lower()

            if exact_match:
                exact_correct += 1
            if ci_match:
                ci_correct += 1
            if ci_match and not exact_match:
                case_only_errors += 1
                details.append((truth, result, "case-only"))

        total = len(SAMPLES)

        print("\n" + "=" * 60)
        print("CASE SENSITIVITY ANALYSIS")
        print("=" * 60)
        print(f"Case-sensitive accuracy:   {exact_correct}/{total} = {exact_correct/total:.0%}")
        print(f"Case-insensitive accuracy: {ci_correct}/{total} = {ci_correct/total:.0%}")
        print(f"Case-only errors:          {case_only_errors}")

        if case_only_errors > 0:
            print(f"\nIf RUNT were case-insensitive, accuracy would improve by "
                  f"{(ci_correct - exact_correct) / total:.0%}")
            print("\nCase-only errors:")
            for truth, result, _ in details:
                print(f"  Truth: {truth!r}  Got: {result!r}")

        assert True


# ---------------------------------------------------------------------------
# 5. Character position analysis — which position has worst accuracy?
# ---------------------------------------------------------------------------

@pytest.mark.skipif(len(SAMPLES) == 0, reason="No captcha fixtures")
class TestPositionAnalysis:
    """Analyze accuracy by character position (1st, 2nd, 3rd, 4th, 5th)."""

    def test_accuracy_by_position(self):
        """Characters at the edges of captcha images are often harder to read."""
        position_stats = defaultdict(lambda: {"correct": 0, "total": 0})

        for sample in SAMPLES:
            result = SOLVER.solve(sample["image_bytes"])
            truth = sample["ground_truth"]

            for i in range(min(len(result), len(truth))):
                position_stats[i + 1]["total"] += 1
                if result[i] == truth[i]:
                    position_stats[i + 1]["correct"] += 1

        print("\n" + "=" * 60)
        print("ACCURACY BY CHARACTER POSITION")
        print("=" * 60)
        print(f"{'Position':<12} {'Correct':<10} {'Total':<8} {'Accuracy'}")
        print("-" * 40)

        weakest_pos = None
        weakest_acc = 1.0

        for pos in sorted(position_stats.keys()):
            stats = position_stats[pos]
            acc = stats["correct"] / stats["total"] if stats["total"] > 0 else 0
            marker = " <<<" if acc < 0.8 else ""
            print(f"  {pos:<10} {stats['correct']:<10} {stats['total']:<8} {acc:.0%}{marker}")
            if acc < weakest_acc:
                weakest_acc = acc
                weakest_pos = pos

        if weakest_pos:
            print(f"\nWeakest position: {weakest_pos} ({weakest_acc:.0%})")
            if weakest_pos in (1, 5):
                print("INSIGHT: Edge characters are weaker — consider padding the image "
                      "or cropping margins before OCR.")

        assert True


# ---------------------------------------------------------------------------
# 6. Character class breakdown (digits vs lowercase vs uppercase)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(len(SAMPLES) == 0, reason="No captcha fixtures")
class TestCharacterClassAccuracy:
    """Compare accuracy across digit, lowercase, and uppercase characters."""

    def test_accuracy_by_class(self):
        """Some character classes may be harder for OCR than others."""
        class_stats = defaultdict(lambda: {"correct": 0, "total": 0})

        for sample in SAMPLES:
            result = SOLVER.solve(sample["image_bytes"])
            truth = sample["ground_truth"]

            for i in range(min(len(result), len(truth))):
                char = truth[i]
                if char.isdigit():
                    cls = "digit"
                elif char.islower():
                    cls = "lowercase"
                elif char.isupper():
                    cls = "UPPERCASE"
                else:
                    cls = "other"

                class_stats[cls]["total"] += 1
                if result[i] == truth[i]:
                    class_stats[cls]["correct"] += 1

        print("\n" + "=" * 60)
        print("ACCURACY BY CHARACTER CLASS")
        print("=" * 60)
        print(f"{'Class':<12} {'Correct':<10} {'Total':<8} {'Accuracy'}")
        print("-" * 40)
        for cls in ["digit", "lowercase", "UPPERCASE"]:
            stats = class_stats.get(cls, {"correct": 0, "total": 0})
            if stats["total"] > 0:
                acc = stats["correct"] / stats["total"]
                marker = " <<<" if acc < 0.8 else ""
                print(f"{cls:<12} {stats['correct']:<10} {stats['total']:<8} {acc:.0%}{marker}")

        assert True


# ---------------------------------------------------------------------------
# 7. Timing analysis — where is time spent?
# ---------------------------------------------------------------------------

@pytest.mark.skipif(len(SAMPLES) == 0, reason="No captcha fixtures")
class TestTimingAnalysis:
    """Profile where time is spent in the OCR pipeline."""

    def test_solve_timing(self):
        """Measure total solve time and identify slow samples."""
        times = []

        for sample in SAMPLES:
            start = time.monotonic()
            SOLVER.solve(sample["image_bytes"])
            elapsed = (time.monotonic() - start) * 1000
            times.append((sample["id"][:12], elapsed, sample["size_bytes"]))

        avg = sum(t for _, t, _ in times) / len(times)
        p95 = sorted(t for _, t, _ in times)[int(len(times) * 0.95)]
        slowest = max(times, key=lambda x: x[1])

        print("\n" + "=" * 60)
        print("TIMING ANALYSIS")
        print("=" * 60)
        print(f"Average solve time: {avg:.0f}ms")
        print(f"P95 solve time:     {p95:.0f}ms")
        print(f"Slowest:            {slowest[0]} ({slowest[1]:.0f}ms, {slowest[2]} bytes)")

        # Check correlation between image size and solve time
        large = [(t, s) for _, t, s in times if s > 8000]
        small = [(t, s) for _, t, s in times if s <= 5000]
        if large and small:
            avg_large = sum(t for t, _ in large) / len(large)
            avg_small = sum(t for t, _ in small) / len(small)
            print(f"\nLarge images (>8KB):  avg {avg_large:.0f}ms  (n={len(large)})")
            print(f"Small images (<=5KB): avg {avg_small:.0f}ms  (n={len(small)})")
            if avg_large > avg_small * 2:
                print("INSIGHT: Large images are significantly slower. Consider resizing "
                      "to a fixed dimension before preprocessing.")

        # Flag if any captcha takes >500ms
        slow = [(cid, t) for cid, t, _ in times if t > 500]
        if slow:
            print(f"\nWARNING: {len(slow)} captchas take >500ms:")
            for cid, t in slow:
                print(f"  {cid}: {t:.0f}ms")

        assert True


# ---------------------------------------------------------------------------
# 8. Stability test — does the same image give the same result?
# ---------------------------------------------------------------------------

@pytest.mark.skipif(len(SAMPLES) == 0, reason="No captcha fixtures")
class TestStability:
    """Test whether OCR gives consistent results for the same image."""

    def test_determinism(self):
        """Run OCR 3 times on each image — results should be identical."""
        unstable = []

        for sample in SAMPLES[:10]:  # Limit to 10 for speed
            results = set()
            for _ in range(3):
                result = SOLVER.solve(sample["image_bytes"])
                results.add(result)
            if len(results) > 1:
                unstable.append((sample["id"][:12], results))

        print("\n" + "=" * 60)
        print("STABILITY TEST (3 runs per image)")
        print("=" * 60)

        if unstable:
            print(f"WARNING: {len(unstable)} images gave inconsistent results:")
            for cid, results in unstable:
                print(f"  {cid}: {results}")
            print("\nINSIGHT: Non-deterministic results suggest the confidence-based "
                  "pipeline selection is sensitive to minor variations. Consider "
                  "majority voting across pipelines instead of max-confidence.")
        else:
            print("All images gave consistent results across 3 runs.")

        assert True


# ---------------------------------------------------------------------------
# 9. Preprocessing gap analysis — what characters have NO good pipeline?
# ---------------------------------------------------------------------------

@pytest.mark.skipif(len(SAMPLES) == 0, reason="No captcha fixtures")
class TestPreprocessingGaps:
    """Find captchas where ALL pipelines fail — no correct answer available."""

    def test_find_unsolvable_captchas(self):
        """Identify captchas that no preprocessing variant can solve correctly."""
        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            pytest.skip("pytesseract/Pillow not available")

        ocr_config = (
            "--psm 8 -c tessedit_char_whitelist="
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        )

        unsolvable = []
        partially_solved = []

        for sample in SAMPLES:
            truth = sample["ground_truth"]
            img = Image.open(io.BytesIO(sample["image_bytes"]))

            pipeline_results = []
            any_exact = False
            best_char_acc = 0

            for preprocessed in OCRSolver._preprocess_variants(img):
                text = pytesseract.image_to_string(preprocessed, config=ocr_config).strip()
                text = re.sub(r"[^a-zA-Z0-9]", "", text)[:5]
                pipeline_results.append(text)

                if text == truth:
                    any_exact = True

                # Character accuracy
                correct = sum(1 for a, b in zip(text, truth) if a == b)
                char_acc = correct / len(truth) if truth else 0
                best_char_acc = max(best_char_acc, char_acc)

            if not any_exact:
                entry = {
                    "id": sample["id"][:12],
                    "truth": truth,
                    "pipelines": pipeline_results,
                    "best_char_acc": best_char_acc,
                }
                if best_char_acc < 0.6:
                    unsolvable.append(entry)
                else:
                    partially_solved.append(entry)

        print("\n" + "=" * 60)
        print("PREPROCESSING GAP ANALYSIS")
        print("=" * 60)

        if unsolvable:
            print(f"\nUNSOLVABLE ({len(unsolvable)} captchas — no pipeline gets >60% chars right):")
            for e in unsolvable:
                print(f"  {e['id']}: truth={e['truth']!r}")
                for i, p in enumerate(e["pipelines"]):
                    print(f"           pipeline_{i+1}: {p!r}")

        if partially_solved:
            print(f"\nPARTIALLY SOLVED ({len(partially_solved)} captchas — some chars right, "
                  "no exact match):")
            for e in partially_solved:
                print(f"  {e['id']}: truth={e['truth']!r}  best_char_acc={e['best_char_acc']:.0%}")
                for i, p in enumerate(e["pipelines"]):
                    match = "  " + "".join(
                        "^" if a != b else " " for a, b in zip(p, e["truth"])
                    )
                    print(f"           pipeline_{i+1}: {p!r}{match}")

        total_unsolvable = len(unsolvable) + len(partially_solved)
        total = len(SAMPLES)
        print(f"\n{total - total_unsolvable}/{total} solvable by at least one pipeline")

        if partially_solved:
            print("\nINSIGHT: Partially solved captchas might benefit from:")
            print("  - Character-level voting across pipelines (not word-level)")
            print("  - Additional preprocessing variants (morphological ops, dilation)")
            print("  - Post-OCR correction using character bigram probabilities")

        assert True


# ---------------------------------------------------------------------------
# 10. Ensemble voting potential — could combining pipelines do better?
# ---------------------------------------------------------------------------

@pytest.mark.skipif(len(SAMPLES) == 0, reason="No captcha fixtures")
class TestEnsembleVoting:
    """Test if character-level majority voting across pipelines improves accuracy."""

    def test_voting_vs_confidence(self):
        """Compare max-confidence selection vs character-level majority voting."""
        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            pytest.skip("pytesseract/Pillow not available")

        ocr_config = (
            "--psm 8 -c tessedit_char_whitelist="
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        )

        confidence_correct = 0
        voting_correct = 0

        for sample in SAMPLES:
            truth = sample["ground_truth"]
            img = Image.open(io.BytesIO(sample["image_bytes"]))

            pipeline_results = []
            pipeline_confs = []

            for preprocessed in OCRSolver._preprocess_variants(img):
                text = pytesseract.image_to_string(preprocessed, config=ocr_config).strip()
                text = re.sub(r"[^a-zA-Z0-9]", "", text)[:5]

                try:
                    data = pytesseract.image_to_data(
                        preprocessed, config=ocr_config, output_type=pytesseract.Output.DICT,
                    )
                    confidences = [int(c) for c in data["conf"] if int(c) > 0]
                    avg_conf = sum(confidences) / len(confidences) if confidences else 0
                except Exception:
                    avg_conf = 0

                pipeline_results.append(text)
                pipeline_confs.append(avg_conf)

            # Strategy 1: Max confidence (current approach)
            best_idx = pipeline_confs.index(max(pipeline_confs))
            conf_result = pipeline_results[best_idx]
            if conf_result == truth:
                confidence_correct += 1

            # Strategy 2: Character-level majority voting
            max_len = max(len(r) for r in pipeline_results) if pipeline_results else 0
            voted = []
            for pos in range(min(max_len, 5)):
                chars_at_pos = [r[pos] for r in pipeline_results if pos < len(r)]
                if chars_at_pos:
                    most_common = Counter(chars_at_pos).most_common(1)[0][0]
                    voted.append(most_common)
            voted_result = "".join(voted)
            if voted_result == truth:
                voting_correct += 1

        total = len(SAMPLES)

        print("\n" + "=" * 60)
        print("ENSEMBLE VOTING vs CONFIDENCE SELECTION")
        print("=" * 60)
        print(f"Max-confidence accuracy: {confidence_correct}/{total} = "
              f"{confidence_correct/total:.0%}")
        print(f"Majority-voting accuracy: {voting_correct}/{total} = "
              f"{voting_correct/total:.0%}")

        diff = voting_correct - confidence_correct
        if diff > 0:
            print(f"\nINSIGHT: Majority voting improves accuracy by {diff} captchas "
                  f"({diff/total:.0%}). Consider switching from confidence-based to "
                  "character-level voting.")
        elif diff < 0:
            print(f"\nConfidence selection is better by {-diff} captchas.")
        else:
            print("\nBoth strategies perform equally.")

        assert True


# ---------------------------------------------------------------------------
# 11. Procuraduria QA coverage — math patterns not yet tested
# ---------------------------------------------------------------------------

class TestProcuraduriaQACoverage:
    """Test edge cases in the Procuraduria captcha solver that aren't covered."""

    def test_math_division(self):
        """Division is not handled — does the system fail gracefully?"""
        from openquery.sources.co.procuraduria import ProcuraduriaSource

        # Division is not in the regex patterns
        try:
            result = ProcuraduriaSource._solve_captcha("¿ Cuanto es 8 / 2 ?")
            # If it returns something, it went to the QA chain
            print(f"\nDivision captcha result: {result!r} (handled by QA chain)")
        except Exception as e:
            print(f"\nDivision captcha error: {e}")

    def test_large_numbers(self):
        """Test with larger numbers that might appear."""
        from openquery.sources.co.procuraduria import ProcuraduriaSource

        assert ProcuraduriaSource._solve_captcha("¿ Cuanto es 12 X 11 ?") == "132"
        assert ProcuraduriaSource._solve_captcha("¿ Cuanto es 99 + 1 ?") == "100"

    def test_spanish_multiplication_word(self):
        """Test 'por' as multiplication operator."""
        from openquery.sources.co.procuraduria import ProcuraduriaSource

        # "por" is not in the regex — this would fall through to QA
        try:
            result = ProcuraduriaSource._solve_captcha("¿ Cuanto es 3 por 4 ?")
            print(f"\n'por' multiplication result: {result!r}")
        except Exception:
            print("\nINSIGHT: 'por' as multiplication operator is NOT handled by regex.")
            print("Consider adding: r'(\\d+)\\s*por\\s*(\\d+)' pattern")

    def test_name_captcha_without_nombre(self):
        """Name-based captcha without nombre should go to QA chain."""
        from openquery.sources.co.procuraduria import ProcuraduriaSource

        try:
            result = ProcuraduriaSource._solve_captcha(
                "¿Escriba las dos primeras letras del primer nombre?",
                nombre="",  # No name provided
            )
            print(f"\nName captcha without nombre: {result!r}")
        except Exception as e:
            print(f"\nName captcha without nombre error: {type(e).__name__}: {e}")

    def test_accent_handling(self):
        """Verify 'sin tilde' directive is respected in QA prompt."""
        from openquery.core.llm import SYSTEM_PROMPT

        prompt = SYSTEM_PROMPT.format(question="¿Capital de Boyaca (sin tilde)?")
        assert "sin tilde" in prompt.lower() or "omit accents" in prompt.lower(), (
            "System prompt does not mention accent handling"
        )

    def test_math_with_extra_spaces(self):
        """Test math captchas with unusual spacing."""
        from openquery.sources.co.procuraduria import ProcuraduriaSource

        assert ProcuraduriaSource._solve_captcha("¿ Cuanto es  5  X  5  ?") == "25"
        assert ProcuraduriaSource._solve_captcha("¿Cuanto es 3+4?") == "7"

    def test_zero_multiplication(self):
        """Edge case: multiplication by zero."""
        from openquery.sources.co.procuraduria import ProcuraduriaSource

        assert ProcuraduriaSource._solve_captcha("¿ Cuanto es 0 X 5 ?") == "0"

    def test_negative_subtraction(self):
        """Edge case: subtraction resulting in negative number."""
        from openquery.sources.co.procuraduria import ProcuraduriaSource

        assert ProcuraduriaSource._solve_captcha("¿ Cuanto es 3 - 7 ?") == "-4"


# ---------------------------------------------------------------------------
# 12. Image complexity correlation
# ---------------------------------------------------------------------------

@pytest.mark.skipif(len(SAMPLES) == 0, reason="No captcha fixtures")
class TestImageComplexity:
    """Analyze if image file size (proxy for visual complexity) correlates with errors."""

    def test_size_vs_accuracy(self):
        """Larger images (more noise/complexity) might be harder to solve."""
        correct_sizes = []
        wrong_sizes = []

        for sample in SAMPLES:
            result = SOLVER.solve(sample["image_bytes"])
            truth = sample["ground_truth"]
            size = sample["size_bytes"]

            if result == truth:
                correct_sizes.append(size)
            else:
                wrong_sizes.append(size)

        print("\n" + "=" * 60)
        print("IMAGE SIZE vs ACCURACY")
        print("=" * 60)

        if correct_sizes:
            avg_correct = sum(correct_sizes) / len(correct_sizes)
            print(f"Correctly solved:  avg={avg_correct:.0f}B (n={len(correct_sizes)})")

        if wrong_sizes:
            avg_wrong = sum(wrong_sizes) / len(wrong_sizes)
            print(f"Incorrectly solved: avg size = {avg_wrong:.0f} bytes  (n={len(wrong_sizes)})")

            if correct_sizes:
                avg_correct = sum(correct_sizes) / len(correct_sizes)
                if avg_wrong > avg_correct * 1.5:
                    print("\nINSIGHT: Failed captchas have significantly larger images.")
                    print("This suggests more complex/noisy images are harder.")
                    print("Consider: adaptive preprocessing based on image complexity.")

        assert True
