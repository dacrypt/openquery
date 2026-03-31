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

    Uses multiple preprocessing pipelines and picks the best result
    based on confidence scoring. This handles the common confusion pairs
    (5/S, c/e, T/I, 8/B) that single-pass OCR struggles with.
    """

    def __init__(self, max_chars: int = 5) -> None:
        self._max_chars = max_chars

    def solve(self, image_bytes: bytes, **hints: str) -> str:
        try:
            import pytesseract  # noqa: F401
            from PIL import Image
        except ImportError as e:
            raise ImportError(
                "pytesseract and Pillow are required for OCR captcha solving. "
                "Install: brew install tesseract && pip install pytesseract Pillow"
            ) from e

        max_chars = int(hints.get("length", self._max_chars))
        img = Image.open(io.BytesIO(image_bytes))

        candidates = []
        for preprocessed in self._preprocess_variants(img):
            text, conf = self._ocr_with_confidence(preprocessed, pytesseract)
            text = re.sub(r"[^a-zA-Z0-9]", "", text.strip())
            if len(text) >= 3:
                candidates.append((text[:max_chars], conf))

        if not candidates:
            from openquery.exceptions import CaptchaError

            raise CaptchaError("ocr", "OCR returned too few characters from all pipelines")

        # Pick candidate with highest confidence
        best_text, best_conf = max(candidates, key=lambda x: x[1])
        logger.debug("OCR candidates: %s, best: '%s' (%.1f)", candidates, best_text, best_conf)
        return best_text

    @staticmethod
    def _preprocess_variants(img):
        """Generate multiple preprocessed versions of the image.

        Different thresholds and filters help with different character shapes.
        """
        from PIL import Image, ImageFilter, ImageOps

        gray = img.convert("L")
        contrasted = ImageOps.autocontrast(gray)

        # Pipeline 1: Standard (threshold=128, 3x scale, median blur)
        p1 = contrasted.point(lambda x: 255 if x > 128 else 0, "1")
        p1 = p1.resize((p1.width * 3, p1.height * 3), Image.LANCZOS)
        p1 = p1.filter(ImageFilter.MedianFilter(3))
        yield p1

        # Pipeline 2: Lower threshold (captures thinner strokes, helps 5/S, T/I)
        p2 = contrasted.point(lambda x: 255 if x > 100 else 0, "1")
        p2 = p2.resize((p2.width * 3, p2.height * 3), Image.LANCZOS)
        p2 = p2.filter(ImageFilter.MedianFilter(3))
        yield p2

        # Pipeline 3: Higher threshold + sharpen (reduces noise, helps 8/B, c/e)
        p3 = contrasted.point(lambda x: 255 if x > 160 else 0, "1")
        p3 = p3.resize((p3.width * 4, p3.height * 4), Image.LANCZOS)
        p3 = p3.filter(ImageFilter.SHARPEN)
        yield p3

    @staticmethod
    def _ocr_with_confidence(img, pytesseract) -> tuple[str, float]:
        """Run OCR and return (text, confidence).

        Uses image_to_string for text and image_to_data for confidence.
        """
        ocr_config = (
            "--psm 8 -c tessedit_char_whitelist="
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        )

        # Get the text
        text = pytesseract.image_to_string(img, config=ocr_config).strip()

        # Get confidence from image_to_data
        try:
            data = pytesseract.image_to_data(
                img, config=ocr_config, output_type=pytesseract.Output.DICT
            )
            confidences = [int(c) for c in data["conf"] if int(c) > 0]
            avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        except Exception:
            avg_conf = 50.0  # Default if confidence extraction fails

        return text, avg_conf


class TrOCRSolver(CaptchaSolver):
    """Solve captchas using Microsoft's TrOCR transformer model.

    Uses the pretrained trocr-small-printed model (~130MB) for high-accuracy
    printed text recognition. Significantly better than tesseract for
    ambiguous characters (5/S, 8/B, T/I, c/e).

    First call downloads the model from HuggingFace and caches it locally.
    Subsequent calls are fast (~50-200ms per image on CPU).
    """

    def __init__(self, model_name: str = "microsoft/trocr-small-printed", max_chars: int = 5):
        self._model_name = model_name
        self._max_chars = max_chars
        self._processor = None
        self._model = None

    def _load_model(self):
        """Lazy-load the TrOCR model on first use."""
        if self._processor is not None:
            return

        try:
            from transformers import TrOCRProcessor, VisionEncoderDecoderModel
        except ImportError as e:
            raise ImportError(
                "transformers and torch are required for TrOCR. "
                "Install: pip install 'openquery[trocr]'"
            ) from e

        logger.info("Loading TrOCR model '%s'...", self._model_name)
        self._processor = TrOCRProcessor.from_pretrained(self._model_name)
        self._model = VisionEncoderDecoderModel.from_pretrained(self._model_name)
        logger.info("TrOCR model loaded")

    def solve(self, image_bytes: bytes, **hints: str) -> str:
        from PIL import Image

        self._load_model()

        max_chars = int(hints.get("length", self._max_chars))
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        pixel_values = self._processor(images=img, return_tensors="pt").pixel_values
        generated_ids = self._model.generate(pixel_values)
        text = self._processor.batch_decode(generated_ids, skip_special_tokens=True)[0]

        # Clean to alphanumeric only
        text = re.sub(r"[^a-zA-Z0-9]", "", text.strip())

        if len(text) < 3:
            from openquery.exceptions import CaptchaError

            raise CaptchaError("trocr", f"TrOCR returned too few characters: '{text}'")

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
