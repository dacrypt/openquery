"""Unit tests for captcha solvers."""

from __future__ import annotations

import pytest

from openquery.core.captcha import CaptchaSolver, ChainedSolver
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
