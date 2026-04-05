"""Captcha solving strategies.

Image captchas (CaptchaSolver):
- OCRSolver: Local pytesseract-based solving (free, no network)
- PaddleOCRSolver, EasyOCRSolver, TrOCRSolver: ML-based solvers
- TwoCaptchaSolver: Paid 2captcha.com API
- VotingSolver: Character-level majority voting
- ChainedSolver: Try solvers in order, first success wins

reCAPTCHA v2 (RecaptchaV2Solver):
- TaskBasedRecaptchaSolver: CapSolver, CapMonster, Anti-Captcha (createTask API)
- TwoCaptchaRecaptchaSolver: 2Captcha API for reCAPTCHA v2
- ChainedRecaptchaSolver: Try multiple reCAPTCHA solvers in order
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


class LLMCaptchaSolver(CaptchaSolver):
    """Solve captchas using a visual LLM (Claude, GPT-4V, etc.).

    Sends the captcha image to an LLM with vision capabilities and asks it to
    read the text. Works as a free/cheap fallback when OCR solvers fail and
    no paid captcha service is configured.

    Supports:
    - Anthropic Claude (claude-sonnet-4-20250514) via ANTHROPIC_API_KEY
    - OpenAI GPT-4o via OPENAI_API_KEY

    The solver auto-detects which API key is available.
    """

    def __init__(self, max_chars: int = 6) -> None:
        self._max_chars = max_chars

    def solve(self, image_bytes: bytes, **hints: str) -> str:
        import base64
        import os

        from openquery.exceptions import CaptchaError

        max_chars = int(hints.get("length", self._max_chars))
        b64_image = base64.b64encode(image_bytes).decode()

        # Try Anthropic first, then OpenAI
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
        openai_key = os.environ.get("OPENAI_API_KEY", "")

        if anthropic_key:
            return self._solve_anthropic(b64_image, max_chars, anthropic_key)
        if openai_key:
            return self._solve_openai(b64_image, max_chars, openai_key)

        raise CaptchaError(
            "llm",
            "No LLM API key found. Set ANTHROPIC_API_KEY or OPENAI_API_KEY.",
        )

    def _solve_anthropic(self, b64_image: str, max_chars: int, api_key: str) -> str:
        import httpx

        from openquery.exceptions import CaptchaError

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-sonnet-4-20250514",
                        "max_tokens": 50,
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "image",
                                        "source": {
                                            "type": "base64",
                                            "media_type": "image/png",
                                            "data": b64_image,
                                        },
                                    },
                                    {
                                        "type": "text",
                                        "text": (
                                            "Read the captcha text in this image. "
                                            "Reply with ONLY the characters, nothing else. "
                                            "No spaces, no quotes, no explanation."
                                        ),
                                    },
                                ],
                            }
                        ],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                text = data["content"][0]["text"].strip()
                text = re.sub(r"[^a-zA-Z0-9]", "", text)

                if len(text) < 3:
                    raise CaptchaError("llm_anthropic", f"LLM returned too few chars: '{text}'")

                logger.info("LLM (Claude) captcha result: '%s'", text[:max_chars])
                return text[:max_chars]
        except CaptchaError:
            raise
        except Exception as e:
            raise CaptchaError("llm_anthropic", f"Anthropic API failed: {e}") from e

    def _solve_openai(self, b64_image: str, max_chars: int, api_key: str) -> str:
        import httpx

        from openquery.exceptions import CaptchaError

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "gpt-4o-mini",
                        "max_tokens": 50,
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/png;base64,{b64_image}",
                                        },
                                    },
                                    {
                                        "type": "text",
                                        "text": (
                                            "Read the captcha text in this image. "
                                            "Reply with ONLY the characters, nothing else. "
                                            "No spaces, no quotes, no explanation."
                                        ),
                                    },
                                ],
                            }
                        ],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                text = data["choices"][0]["message"]["content"].strip()
                text = re.sub(r"[^a-zA-Z0-9]", "", text)

                if len(text) < 3:
                    raise CaptchaError("llm_openai", f"LLM returned too few chars: '{text}'")

                logger.info("LLM (GPT-4o) captcha result: '%s'", text[:max_chars])
                return text[:max_chars]
        except CaptchaError:
            raise
        except Exception as e:
            raise CaptchaError("llm_openai", f"OpenAI API failed: {e}") from e


class TwoCaptchaSolver(CaptchaSolver):
    """Solve image CAPTCHAs using the 2captcha.com paid service."""

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


# ---------------------------------------------------------------------------
# reCAPTCHA v2 solvers
# ---------------------------------------------------------------------------


class RecaptchaV2Solver(ABC):
    """Abstract solver for Google reCAPTCHA v2.

    Unlike image captcha solvers, reCAPTCHA v2 requires a sitekey and page URL
    instead of image bytes. The solver contacts an external service that returns
    a g-recaptcha-response token to inject into the page.
    """

    @abstractmethod
    def solve_recaptcha_v2(self, sitekey: str, page_url: str) -> str:
        """Solve a reCAPTCHA v2 challenge.

        Args:
            sitekey: The reCAPTCHA data-sitekey from the page HTML.
            page_url: The full URL of the page containing the captcha.

        Returns:
            A g-recaptcha-response token string.

        Raises:
            CaptchaError: If solving fails.
        """


class TaskBasedRecaptchaSolver(RecaptchaV2Solver):
    """Solve reCAPTCHA v2 via Anti-Captcha-compatible APIs.

    Works with CapSolver, CapMonster, and Anti-Captcha — all use the same
    createTask/getTaskResult JSON API pattern.

    Providers:
        CapSolver:    https://api.capsolver.com      (~$1/1000 solves, AI-based)
        CapMonster:   https://api.capmonster.cloud    (~$0.80/1000, AI-based)
        Anti-Captcha: https://api.anti-captcha.com    (~$2/1000, human workers)
    """

    PROVIDER_URLS = {
        "capsolver": "https://api.capsolver.com",
        "capmonster": "https://api.capmonster.cloud",
        "anticaptcha": "https://api.anti-captcha.com",
    }

    # Task type naming varies slightly per provider
    TASK_TYPES = {
        "capsolver": "ReCaptchaV2TaskProxyLess",
        "capmonster": "NoCaptchaTaskProxyless",
        "anticaptcha": "NoCaptchaTaskProxyless",
    }

    def __init__(
        self,
        api_key: str,
        provider: str = "capsolver",
        poll_interval: float = 5.0,
        max_wait: float = 120.0,
    ) -> None:
        self._api_key = api_key
        self._provider = provider.lower()
        self._base_url = self.PROVIDER_URLS.get(
            self._provider, provider  # allow raw URL
        )
        self._task_type = self.TASK_TYPES.get(self._provider, "NoCaptchaTaskProxyless")
        self._poll_interval = poll_interval
        self._max_wait = max_wait

    def solve_recaptcha_v2(self, sitekey: str, page_url: str) -> str:
        import time

        import httpx

        from openquery.exceptions import CaptchaError

        # Step 1: Create task
        create_payload = {
            "clientKey": self._api_key,
            "task": {
                "type": self._task_type,
                "websiteURL": page_url,
                "websiteKey": sitekey,
            },
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(
                    f"{self._base_url}/createTask", json=create_payload
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            raise CaptchaError(
                self._provider, f"createTask failed: {e}"
            ) from e

        error_id = data.get("errorId", 0)
        if error_id:
            raise CaptchaError(
                self._provider,
                f"createTask error: {data.get('errorDescription', 'unknown')}",
            )

        task_id = data.get("taskId")
        if not task_id:
            raise CaptchaError(self._provider, "No taskId in createTask response")

        logger.info(
            "%s: created task %s for sitekey=%s",
            self._provider,
            task_id,
            sitekey[:20],
        )

        # Step 2: Poll for result
        poll_payload = {"clientKey": self._api_key, "taskId": task_id}
        elapsed = 0.0

        while elapsed < self._max_wait:
            time.sleep(self._poll_interval)
            elapsed += self._poll_interval

            try:
                with httpx.Client(timeout=30.0) as client:
                    resp = client.post(
                        f"{self._base_url}/getTaskResult", json=poll_payload
                    )
                    resp.raise_for_status()
                    result = resp.json()
            except Exception as e:
                logger.warning("%s: poll error: %s", self._provider, e)
                continue

            status = result.get("status", "")
            if status == "ready":
                solution = result.get("solution", {})
                token = solution.get("gRecaptchaResponse", "")
                if token:
                    logger.info(
                        "%s: solved in %.0fs (token=%s...)",
                        self._provider,
                        elapsed,
                        token[:30],
                    )
                    return token
                raise CaptchaError(
                    self._provider, "No gRecaptchaResponse in solution"
                )

            if result.get("errorId"):
                raise CaptchaError(
                    self._provider,
                    f"Task error: {result.get('errorDescription', 'unknown')}",
                )

            logger.debug(
                "%s: task %s status=%s (%.0fs elapsed)",
                self._provider,
                task_id,
                status,
                elapsed,
            )

        raise CaptchaError(
            self._provider,
            f"Timeout after {self._max_wait}s waiting for solution",
        )


class TwoCaptchaRecaptchaSolver(RecaptchaV2Solver):
    """Solve reCAPTCHA v2 using the 2Captcha API.

    Price: ~$2.99/1000 solves. Uses human workers (15-45s typical).
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def solve_recaptcha_v2(self, sitekey: str, page_url: str) -> str:
        from openquery.exceptions import CaptchaError

        try:
            from twocaptcha import TwoCaptcha
        except ImportError as e:
            raise CaptchaError(
                "2captcha",
                "python-2captcha is required. Install: pip install 2captcha-python",
            ) from e

        solver = TwoCaptcha(self._api_key)
        try:
            result = solver.recaptcha(sitekey=sitekey, url=page_url)
            token = result.get("code", "")
            if not token:
                raise CaptchaError("2captcha", "No code in 2captcha response")
            logger.info("2captcha: solved (token=%s...)", token[:30])
            return token
        except CaptchaError:
            raise
        except Exception as e:
            raise CaptchaError("2captcha", f"2captcha failed: {e}") from e


class ChainedRecaptchaSolver(RecaptchaV2Solver):
    """Try multiple reCAPTCHA v2 solvers in order. First success wins."""

    def __init__(self, solvers: list[RecaptchaV2Solver]) -> None:
        self._solvers = solvers

    def solve_recaptcha_v2(self, sitekey: str, page_url: str) -> str:
        from openquery.exceptions import CaptchaError

        last_error: Exception | None = None
        for solver in self._solvers:
            try:
                return solver.solve_recaptcha_v2(sitekey, page_url)
            except Exception as e:
                logger.warning(
                    "RecaptchaSolver %s failed: %s", type(solver).__name__, e
                )
                last_error = e

        raise CaptchaError(
            "chained_recaptcha",
            f"All reCAPTCHA solvers failed. Last: {last_error}",
        )


# ---------------------------------------------------------------------------
# reCAPTCHA v2 helpers
# ---------------------------------------------------------------------------


def extract_recaptcha_sitekey(page) -> str | None:
    """Extract reCAPTCHA v2 sitekey from a Playwright page.

    Looks for data-sitekey attribute on reCAPTCHA div or iframe src parameter.
    """
    sitekey = page.evaluate("""() => {
        // Try data-sitekey attribute
        var el = document.querySelector('[data-sitekey]');
        if (el) return el.getAttribute('data-sitekey');
        // Try reCAPTCHA iframe src
        var iframe = document.querySelector('iframe[src*="recaptcha"]');
        if (iframe) {
            var match = iframe.src.match(/[?&]k=([^&]+)/);
            if (match) return match[1];
        }
        // Try reCAPTCHA script render param
        var script = document.querySelector('script[src*="recaptcha/api.js"]');
        if (script) {
            var src = script.src;
            var match = src.match(/[?&]render=([^&]+)/);
            if (match && match[1] !== 'explicit') return match[1];
        }
        return null;
    }""")
    return sitekey


def inject_recaptcha_token(page, token: str) -> None:
    """Inject a g-recaptcha-response token into a Playwright page.

    Sets the hidden textarea value and attempts to trigger common callbacks.
    """
    page.evaluate("""(token) => {
        // Set all g-recaptcha-response textareas (some pages have multiple)
        var textareas = document.querySelectorAll(
            '#g-recaptcha-response, [name="g-recaptcha-response"], '
            + 'textarea[id*="g-recaptcha-response"]'
        );
        textareas.forEach(ta => {
            ta.style.display = 'block';
            ta.value = token;
        });

        // Try to trigger reCAPTCHA callback
        try {
            if (typeof ___grecaptcha_cfg !== 'undefined') {
                var clients = ___grecaptcha_cfg.clients;
                for (var key in clients) {
                    var client = clients[key];
                    // Walk the client object to find callback
                    var queue = [client];
                    while (queue.length > 0) {
                        var obj = queue.shift();
                        if (!obj || typeof obj !== 'object') continue;
                        for (var prop in obj) {
                            if (prop === 'callback' && typeof obj[prop] === 'function') {
                                obj[prop](token);
                                return;
                            }
                            if (typeof obj[prop] === 'object' && obj[prop] !== null) {
                                queue.push(obj[prop]);
                            }
                        }
                    }
                }
            }
        } catch (e) {
            // Callback trigger is best-effort
        }
    }""", token)


def build_recaptcha_solver() -> RecaptchaV2Solver | None:
    """Build a reCAPTCHA v2 solver chain from environment variables.

    Checks for API keys in order of cost-effectiveness:
    1. OPENQUERY_CAPSOLVER_API_KEY (cheapest, AI-based)
    2. OPENQUERY_CAPMONSTER_API_KEY
    3. OPENQUERY_ANTICAPTCHA_API_KEY
    4. OPENQUERY_TWO_CAPTCHA_API_KEY

    Returns None if no API keys are configured.
    """
    from openquery.config import get_settings

    settings = get_settings()
    solvers: list[RecaptchaV2Solver] = []

    if settings.capsolver_api_key:
        solvers.append(
            TaskBasedRecaptchaSolver(settings.capsolver_api_key, "capsolver")
        )

    if settings.capmonster_api_key:
        solvers.append(
            TaskBasedRecaptchaSolver(settings.capmonster_api_key, "capmonster")
        )

    if settings.anticaptcha_api_key:
        solvers.append(
            TaskBasedRecaptchaSolver(settings.anticaptcha_api_key, "anticaptcha")
        )

    if settings.two_captcha_api_key:
        solvers.append(
            TwoCaptchaRecaptchaSolver(settings.two_captcha_api_key)
        )

    if not solvers:
        return None
    if len(solvers) == 1:
        return solvers[0]
    return ChainedRecaptchaSolver(solvers)
