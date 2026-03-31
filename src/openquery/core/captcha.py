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


class HuggingFaceOCRSolver(CaptchaSolver):
    """Solve captchas using HuggingFace Inference API (free tier).

    Uses image-to-text models hosted on HuggingFace. Requires HF_TOKEN env var.
    Free tier has rate limits (~30 req/min) but sufficient for captcha volume.

    Note: trocr-base-printed may output uppercase only. Consider using a
    vision-language model if case-sensitive captchas are needed.
    """

    def __init__(
        self,
        model: str = "microsoft/trocr-base-printed",
        max_chars: int = 5,
    ) -> None:
        self._model = model
        self._max_chars = max_chars
        self._client = None

    def _get_client(self):
        """Lazy-load the HuggingFace InferenceClient."""
        if self._client is not None:
            return self._client

        import os

        token = os.environ.get("HF_TOKEN", "")
        if not token:
            from openquery.exceptions import CaptchaError

            raise CaptchaError("hf_ocr", "HF_TOKEN env var required for HuggingFace Inference API")

        try:
            from huggingface_hub import InferenceClient
        except ImportError as e:
            from openquery.exceptions import CaptchaError

            raise CaptchaError(
                "hf_ocr",
                "huggingface_hub is required. Install: pip install 'openquery[huggingface]'",
            ) from e

        self._client = InferenceClient(token=token)
        return self._client

    def solve(self, image_bytes: bytes, **hints: str) -> str:
        from openquery.exceptions import CaptchaError

        client = self._get_client()
        max_chars = int(hints.get("length", self._max_chars))

        try:
            result = client.image_to_text(image_bytes, model=self._model)
            text = re.sub(r"[^a-zA-Z0-9]", "", str(result).strip())

            if len(text) < 3:
                raise CaptchaError("hf_ocr", f"HF OCR returned too few characters: '{text}'")

            logger.info("HuggingFace OCR result: '%s'", text[:max_chars])
            return text[:max_chars]
        except CaptchaError:
            raise
        except Exception as e:
            raise CaptchaError("hf_ocr", f"HuggingFace OCR failed: {e}") from e


class PaddleOCRSolver(CaptchaSolver):
    """Solve captchas using PaddleOCR PP-OCRv5.

    Uses PaddlePaddle's PP-OCRv5 model for extremely high accuracy on printed
    alphanumeric captchas. Achieves ~100% on test fixtures vs ~80-85% for
    Tesseract/EasyOCR.

    First call downloads models (~50MB) from HuggingFace and caches locally.
    Subsequent calls: ~130ms per image on CPU.
    """

    def __init__(self, max_chars: int = 5) -> None:
        self._max_chars = max_chars
        self._ocr = None

    def _get_ocr(self):
        """Lazy-load the PaddleOCR engine on first use."""
        if self._ocr is not None:
            return self._ocr

        try:
            from paddleocr import PaddleOCR
        except ImportError as e:
            from openquery.exceptions import CaptchaError

            raise CaptchaError(
                "paddleocr",
                "paddleocr is required. Install: pip install 'openquery[paddleocr]'",
            ) from e

        logger.info("Loading PaddleOCR engine...")
        self._ocr = PaddleOCR(
            lang="en",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
        logger.info("PaddleOCR engine loaded")
        return self._ocr

    def solve(self, image_bytes: bytes, **hints: str) -> str:
        import tempfile

        from openquery.exceptions import CaptchaError

        ocr = self._get_ocr()
        max_chars = int(hints.get("length", self._max_chars))

        try:
            # PaddleOCR requires a file path, write temp file
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                f.write(image_bytes)
                tmp_path = f.name

            try:
                results = ocr.predict(tmp_path)
            finally:
                import os

                os.unlink(tmp_path)

            # Extract recognized text from results
            texts = []
            for r in results:
                if hasattr(r, "rec_texts"):
                    texts.extend(r.rec_texts)
                elif isinstance(r, dict) and "rec_texts" in r:
                    texts.extend(r["rec_texts"])

            text = "".join(texts)
            text = re.sub(r"[^a-zA-Z0-9]", "", text.strip())

            if len(text) < 3:
                raise CaptchaError(
                    "paddleocr", f"PaddleOCR returned too few characters: '{text}'"
                )

            logger.debug("PaddleOCR result: '%s'", text[:max_chars])
            return text[:max_chars]
        except CaptchaError:
            raise
        except Exception as e:
            raise CaptchaError("paddleocr", f"PaddleOCR failed: {e}") from e


class EasyOCRSolver(CaptchaSolver):
    """Solve captchas using EasyOCR (JaidedAI).

    Uses a CRNN-based model. Generally more accurate and faster than Tesseract
    for printed alphanumeric captchas. Better at distinguishing 8/B and T/I.

    First call downloads the model (~30MB) and caches it locally.
    Subsequent calls: ~100-200ms per image on CPU.
    """

    def __init__(self, max_chars: int = 5) -> None:
        self._max_chars = max_chars
        self._reader = None

    def _get_reader(self):
        """Lazy-load the EasyOCR reader on first use."""
        if self._reader is not None:
            return self._reader

        try:
            import easyocr
        except ImportError as e:
            from openquery.exceptions import CaptchaError

            raise CaptchaError(
                "easyocr",
                "easyocr is required. Install: pip install 'openquery[easyocr]'",
            ) from e

        logger.info("Loading EasyOCR reader...")
        self._reader = easyocr.Reader(["en"], gpu=False, verbose=False)
        logger.info("EasyOCR reader loaded")
        return self._reader

    def solve(self, image_bytes: bytes, **hints: str) -> str:
        from openquery.exceptions import CaptchaError

        reader = self._get_reader()
        max_chars = int(hints.get("length", self._max_chars))

        try:
            results = reader.readtext(
                image_bytes,
                detail=0,
                allowlist="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
            )
            text = "".join(results)
            text = re.sub(r"[^a-zA-Z0-9]", "", text.strip())

            if len(text) < 3:
                raise CaptchaError("easyocr", f"EasyOCR returned too few characters: '{text}'")

            logger.debug("EasyOCR result: '%s'", text[:max_chars])
            return text[:max_chars]
        except CaptchaError:
            raise
        except Exception as e:
            raise CaptchaError("easyocr", f"EasyOCR failed: {e}") from e


class VotingSolver(CaptchaSolver):
    """Character-level majority voting across multiple OCR solvers.

    Runs all child solvers on the same image and picks the most common
    character at each position. This exploits the fact that different engines
    make different mistakes — combining them gives higher accuracy.

    With Tesseract + EasyOCR: 90% accuracy (vs 80%/85% individually).
    """

    def __init__(self, solvers: list[CaptchaSolver]) -> None:
        self._solvers = solvers

    def solve(self, image_bytes: bytes, **hints: str) -> str:
        from collections import Counter

        from openquery.exceptions import CaptchaError

        results = []
        for solver in self._solvers:
            try:
                result = solver.solve(image_bytes, **hints)
                results.append(result)
            except Exception as e:
                logger.warning("VotingSolver: %s failed: %s", type(solver).__name__, e)

        if not results:
            raise CaptchaError("voting", "All solvers failed, no results to vote on")

        if len(results) == 1:
            return results[0]

        # Character-level majority voting
        max_len = max(len(r) for r in results)
        voted = []
        for pos in range(max_len):
            chars = [r[pos] for r in results if pos < len(r)]
            if chars:
                most_common = Counter(chars).most_common(1)[0][0]
                voted.append(most_common)

        text = "".join(voted)
        logger.debug("VotingSolver: inputs=%s → voted='%s'", results, text)
        return text


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
