"""Unit tests for captcha solvers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from openquery.core.captcha import (
    CaptchaSolver,
    ChainedSolver,
    EasyOCRSolver,
    HuggingFaceOCRSolver,
    PaddleOCRSolver,
    VotingSolver,
)
from openquery.exceptions import CaptchaError


class FailingSolver(CaptchaSolver):
    """Always fails — for testing ChainedSolver."""

    def solve(self, image_bytes: bytes, **hints: str) -> str:
        raise CaptchaError("test", "always fails")


class FixedSolver(CaptchaSolver):
    """Always returns a fixed value."""

    def __init__(self, value: str) -> None:
        self._value = value

    def solve(self, image_bytes: bytes, **hints: str) -> str:
        return self._value


class TestChainedSolver:
    def test_first_solver_wins(self):
        solver = ChainedSolver([FixedSolver("abc12"), FixedSolver("xyz99")])
        assert solver.solve(b"dummy") == "abc12"

    def test_fallback_on_failure(self):
        solver = ChainedSolver([FailingSolver(), FixedSolver("xyz99")])
        assert solver.solve(b"dummy") == "xyz99"

    def test_all_fail_raises(self):
        solver = ChainedSolver([FailingSolver(), FailingSolver()])
        with pytest.raises(CaptchaError, match="All solvers failed"):
            solver.solve(b"dummy")


class TestHuggingFaceOCRSolver:
    def test_missing_token_raises_captcha_error(self):
        """Should raise CaptchaError (not ImportError) so ChainedSolver skips it."""
        import os

        old = os.environ.pop("HF_TOKEN", None)
        try:
            solver = HuggingFaceOCRSolver()
            with pytest.raises(CaptchaError, match="HF_TOKEN"):
                solver.solve(b"dummy")
        finally:
            if old:
                os.environ["HF_TOKEN"] = old

    def test_successful_solve(self):
        import os

        os.environ["HF_TOKEN"] = "test-token"
        try:
            solver = HuggingFaceOCRSolver()
            mock_client = MagicMock()
            mock_client.image_to_text.return_value = "aB3x9"

            with patch.object(solver, "_get_client", return_value=mock_client):
                result = solver.solve(b"fake-png-bytes")
                assert result == "aB3x9"
                mock_client.image_to_text.assert_called_once()
        finally:
            os.environ.pop("HF_TOKEN", None)

    def test_too_few_chars_raises(self):
        import os

        os.environ["HF_TOKEN"] = "test-token"
        try:
            solver = HuggingFaceOCRSolver()
            mock_client = MagicMock()
            mock_client.image_to_text.return_value = "ab"  # Only 2 chars

            with patch.object(solver, "_get_client", return_value=mock_client):
                with pytest.raises(CaptchaError, match="too few characters"):
                    solver.solve(b"fake-png-bytes")
        finally:
            os.environ.pop("HF_TOKEN", None)

    def test_truncates_to_max_chars(self):
        import os

        os.environ["HF_TOKEN"] = "test-token"
        try:
            solver = HuggingFaceOCRSolver(max_chars=3)
            mock_client = MagicMock()
            mock_client.image_to_text.return_value = "aBcDe"

            with patch.object(solver, "_get_client", return_value=mock_client):
                result = solver.solve(b"fake-png-bytes")
                assert result == "aBc"
        finally:
            os.environ.pop("HF_TOKEN", None)

    def test_skipped_in_chain_without_token(self):
        """HF solver should be gracefully skipped in ChainedSolver when no token."""
        import os

        old = os.environ.pop("HF_TOKEN", None)
        try:
            solver = ChainedSolver([
                HuggingFaceOCRSolver(),
                FixedSolver("fallback"),
            ])
            assert solver.solve(b"dummy") == "fallback"
        finally:
            if old:
                os.environ["HF_TOKEN"] = old


class TestPaddleOCRSolver:
    def test_successful_solve(self):
        solver = PaddleOCRSolver(max_chars=5)
        mock_ocr = MagicMock()
        # PaddleOCR returns objects with rec_texts attribute
        mock_result = MagicMock()
        mock_result.rec_texts = ["aB3x9"]
        mock_ocr.predict.return_value = [mock_result]

        with patch.object(solver, "_get_ocr", return_value=mock_ocr):
            result = solver.solve(b"fake-png-bytes")
            assert result == "aB3x9"
            mock_ocr.predict.assert_called_once()

    def test_too_few_chars_raises(self):
        solver = PaddleOCRSolver(max_chars=5)
        mock_ocr = MagicMock()
        mock_result = MagicMock()
        mock_result.rec_texts = ["ab"]
        mock_ocr.predict.return_value = [mock_result]

        with patch.object(solver, "_get_ocr", return_value=mock_ocr):
            with pytest.raises(CaptchaError, match="too few characters"):
                solver.solve(b"fake-png-bytes")

    def test_truncates_to_max_chars(self):
        solver = PaddleOCRSolver(max_chars=3)
        mock_ocr = MagicMock()
        mock_result = MagicMock()
        mock_result.rec_texts = ["aBcDe"]
        mock_ocr.predict.return_value = [mock_result]

        with patch.object(solver, "_get_ocr", return_value=mock_ocr):
            result = solver.solve(b"fake-png-bytes")
            assert result == "aBc"

    def test_strips_non_alphanumeric(self):
        solver = PaddleOCRSolver(max_chars=5)
        mock_ocr = MagicMock()
        mock_result = MagicMock()
        mock_result.rec_texts = ["a-B.3!x"]
        mock_ocr.predict.return_value = [mock_result]

        with patch.object(solver, "_get_ocr", return_value=mock_ocr):
            result = solver.solve(b"fake-png-bytes")
            assert result == "aB3x"

    def test_dict_result_format(self):
        """PaddleOCR may return dicts instead of objects."""
        solver = PaddleOCRSolver(max_chars=5)
        mock_ocr = MagicMock()
        mock_ocr.predict.return_value = [{"rec_texts": ["Xn7So"]}]

        with patch.object(solver, "_get_ocr", return_value=mock_ocr):
            result = solver.solve(b"fake-png-bytes")
            assert result == "Xn7So"

    def test_missing_paddleocr_raises_captcha_error(self):
        """Should raise CaptchaError so ChainedSolver can skip it."""
        solver = PaddleOCRSolver()
        solver._ocr = None
        with patch.dict("sys.modules", {"paddleocr": None}):
            with pytest.raises(CaptchaError, match="paddleocr"):
                solver.solve(b"dummy")


class TestEasyOCRSolver:
    def test_successful_solve(self):
        solver = EasyOCRSolver(max_chars=5)
        mock_reader = MagicMock()
        mock_reader.readtext.return_value = ["aB3x9"]

        with patch.object(solver, "_get_reader", return_value=mock_reader):
            result = solver.solve(b"fake-png-bytes")
            assert result == "aB3x9"
            mock_reader.readtext.assert_called_once()

    def test_too_few_chars_raises(self):
        solver = EasyOCRSolver(max_chars=5)
        mock_reader = MagicMock()
        mock_reader.readtext.return_value = ["ab"]

        with patch.object(solver, "_get_reader", return_value=mock_reader):
            with pytest.raises(CaptchaError, match="too few characters"):
                solver.solve(b"fake-png-bytes")

    def test_truncates_to_max_chars(self):
        solver = EasyOCRSolver(max_chars=3)
        mock_reader = MagicMock()
        mock_reader.readtext.return_value = ["aBcDe"]

        with patch.object(solver, "_get_reader", return_value=mock_reader):
            result = solver.solve(b"fake-png-bytes")
            assert result == "aBc"

    def test_strips_non_alphanumeric(self):
        solver = EasyOCRSolver(max_chars=5)
        mock_reader = MagicMock()
        mock_reader.readtext.return_value = ["a-B.3!x"]

        with patch.object(solver, "_get_reader", return_value=mock_reader):
            result = solver.solve(b"fake-png-bytes")
            assert result == "aB3x"

    def test_joins_multiple_results(self):
        solver = EasyOCRSolver(max_chars=5)
        mock_reader = MagicMock()
        mock_reader.readtext.return_value = ["aB", "3x9"]

        with patch.object(solver, "_get_reader", return_value=mock_reader):
            result = solver.solve(b"fake-png-bytes")
            assert result == "aB3x9"

    def test_missing_easyocr_raises_captcha_error(self):
        """Should raise CaptchaError so ChainedSolver can skip it."""
        solver = EasyOCRSolver()
        solver._reader = None
        with patch.dict("sys.modules", {"easyocr": None}):
            with pytest.raises(CaptchaError, match="easyocr"):
                solver.solve(b"dummy")


class TestVotingSolver:
    def test_unanimous_vote(self):
        solver = VotingSolver([FixedSolver("abc12"), FixedSolver("abc12")])
        assert solver.solve(b"dummy") == "abc12"

    def test_majority_wins(self):
        solver = VotingSolver([
            FixedSolver("abc12"),
            FixedSolver("aBc12"),
            FixedSolver("abc12"),
        ])
        # Position 1: a,a,a -> a; pos 2: b,B,b -> b; pos 3: c,c,c -> c
        assert solver.solve(b"dummy") == "abc12"

    def test_single_solver_passthrough(self):
        solver = VotingSolver([FixedSolver("xyz99")])
        assert solver.solve(b"dummy") == "xyz99"

    def test_all_fail_raises(self):
        solver = VotingSolver([FailingSolver(), FailingSolver()])
        with pytest.raises(CaptchaError, match="All solvers failed"):
            solver.solve(b"dummy")

    def test_one_fails_uses_remaining(self):
        solver = VotingSolver([FailingSolver(), FixedSolver("abc12")])
        assert solver.solve(b"dummy") == "abc12"

    def test_character_level_voting_resolves_disagreements(self):
        """When solvers disagree on specific chars, majority wins per position."""
        solver = VotingSolver([
            FixedSolver("5bc12"),  # '5' at pos 0
            FixedSolver("Sbc12"),  # 'S' at pos 0
            FixedSolver("5bc12"),  # '5' at pos 0 — majority
        ])
        assert solver.solve(b"dummy") == "5bc12"

    def test_different_lengths(self):
        """When results have different lengths, votes on available positions."""
        solver = VotingSolver([
            FixedSolver("abc"),
            FixedSolver("abcd"),
        ])
        result = solver.solve(b"dummy")
        assert result.startswith("abc")
        assert len(result) == 4  # max length wins
