"""Face verification using DeepFace.

Provides face comparison (1:1 verification) with optional anti-spoofing
(liveness detection). Uses DeepFace with ArcFace backend for high accuracy
across diverse ethnic groups.

DeepFace is an optional dependency — install with: pip install 'openquery[deepface]'
"""

from __future__ import annotations

import base64
import logging
import tempfile
import time
from pathlib import Path

from openquery.models.face import FaceVerifyResult

logger = logging.getLogger(__name__)


class FaceVerifier:
    """Verify face identity between two images."""

    def __init__(self, model_name: str = "ArcFace") -> None:
        self._model_name = model_name

    def verify(self, image1_bytes: bytes, image2_bytes: bytes) -> FaceVerifyResult:
        """Compare two face images and return verification result."""
        try:
            from deepface import DeepFace
        except ImportError:
            raise ImportError(
                "DeepFace is required for face verification. "
                "Install: pip install 'openquery[deepface]'"
            )

        start = time.monotonic()
        tmp1 = tmp2 = None

        try:
            tmp1 = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            tmp1.write(image1_bytes)
            tmp1.close()

            tmp2 = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            tmp2.write(image2_bytes)
            tmp2.close()

            result = DeepFace.verify(
                img1_path=tmp1.name,
                img2_path=tmp2.name,
                model_name=self._model_name,
                anti_spoofing=True,
            )

            elapsed = int((time.monotonic() - start) * 1000)

            return FaceVerifyResult(
                verified=result.get("verified", False),
                confidence=1.0 - result.get("distance", 1.0),
                distance=result.get("distance", 0.0),
                threshold=result.get("threshold", 0.0),
                model=result.get("model", self._model_name),
                liveness=not result.get("is_real") is False,
                processing_time_ms=elapsed,
            )

        except ImportError:
            raise
        except Exception as e:
            elapsed = int((time.monotonic() - start) * 1000)
            logger.error("Face verification failed: %s", e)
            from openquery.exceptions import FaceVerificationError
            raise FaceVerificationError(str(e)) from e
        finally:
            if tmp1:
                Path(tmp1.name).unlink(missing_ok=True)
            if tmp2:
                Path(tmp2.name).unlink(missing_ok=True)

    def verify_from_base64(self, img1_b64: str, img2_b64: str) -> FaceVerifyResult:
        """Verify faces from base64-encoded images."""
        return self.verify(base64.b64decode(img1_b64), base64.b64decode(img2_b64))

    def verify_from_paths(self, path1: str, path2: str) -> FaceVerifyResult:
        """Verify faces from file paths."""
        return self.verify(Path(path1).read_bytes(), Path(path2).read_bytes())
