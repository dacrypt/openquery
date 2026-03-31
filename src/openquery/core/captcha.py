"""Captcha solving strategies.

Provides an ABC and concrete implementations:
- OCRSolver: Local pytesseract-based solving (free, no network)
- TwoCaptchaSolver: Paid 2captcha.com API (for reCAPTCHA/hCaptcha)
- ChainedSolver: Try solvers in order, first success wins
"""

from __future__ import annotations

import io
import logging
import re
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class CaptchaSolver(ABC):
    """Abstract captcha solver."""

    @abstractmethod
    def solve(self, image_bytes: bytes, **hints: str) -> str:
        """Solve a captcha image.

        Args:
            image_bytes: Raw image bytes (PNG/JPEG).
            **hints: Optional hints (e.g., length=5, charset=alphanumeric).

        Returns:
            Solved captcha text.

        Raises:
            CaptchaError: If solving fails.
        """


class OCRSolver(CaptchaSolver):
    """Solve simple captchas using pytesseract OCR.

    Image processing pipeline (from RUNT):
    1. Convert to grayscale
    2. Auto-contrast enhancement
    3. Threshold to black/white (cutoff=128)
    4. Scale up 3x with LANCZOS resampling
    5. Median blur (3px) to smooth edges
    6. pytesseract with PSM 8 (single word) and alphanumeric whitelist
    """

    def __init__(self, max_chars: int = 5) -> None:
        self._max_chars = max_chars

    def solve(self, image_bytes: bytes, **hints: str) -> str:
        try:
            import pytesseract
            from PIL import Image, ImageFilter, ImageOps
        except ImportError as e:
            raise ImportError(
                "pytesseract and Pillow are required for OCR captcha solving. "
                "Install: brew install tesseract && pip install pytesseract Pillow"
            ) from e

        img = Image.open(io.BytesIO(image_bytes))

        # Pre-process for better OCR
        img = img.convert("L")  # Grayscale
        img = ImageOps.autocontrast(img)  # Enhance contrast
        img = img.point(lambda x: 255 if x > 128 else 0, "1")  # Threshold
        img = img.resize((img.width * 3, img.height * 3), Image.LANCZOS)  # Scale up
        img = img.filter(ImageFilter.MedianFilter(3))  # Smooth edges

        # OCR with restrictive whitelist
        text = pytesseract.image_to_string(
            img,
            config=(
                "--psm 8 -c tessedit_char_whitelist="
                "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
            ),
        )
        text = re.sub(r"[^a-zA-Z0-9]", "", text.strip())

        max_chars = int(hints.get("length", self._max_chars))
        if len(text) < 3:
            from openquery.exceptions import CaptchaError

            raise CaptchaError("ocr", f"OCR returned too few characters: '{text}'")

        return text[:max_chars]


class TwoCaptchaSolver(CaptchaSolver):
    """Solve captchas using the 2captcha.com API."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def solve(self, image_bytes: bytes, **hints: str) -> str:
        try:
            from twocaptcha import TwoCaptcha
        except ImportError as e:
            raise ImportError(
                "python-2captcha is required. Install: pip install python-2captcha"
            ) from e

        import base64

        solver = TwoCaptcha(self._api_key)
        b64 = base64.b64encode(image_bytes).decode()
        result = solver.normal(b64, **hints)
        return result["code"]


class ChainedSolver(CaptchaSolver):
    """Try multiple solvers in order. First success wins."""

    def __init__(self, solvers: list[CaptchaSolver]) -> None:
        self._solvers = solvers

    def solve(self, image_bytes: bytes, **hints: str) -> str:
        last_error: Exception | None = None
        for solver in self._solvers:
            try:
                return solver.solve(image_bytes, **hints)
            except Exception as e:
                logger.warning("Solver %s failed: %s", type(solver).__name__, e)
                last_error = e

        from openquery.exceptions import CaptchaError

        raise CaptchaError("chained", f"All solvers failed. Last: {last_error}")
