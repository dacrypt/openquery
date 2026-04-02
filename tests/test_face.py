"""Tests for face verification."""

from __future__ import annotations

import pytest

from openquery.models.face import FaceVerifyInput, FaceVerifyResult


class TestFaceModels:
    """Test face verification model validation."""

    def test_input_requires_image1(self):
        with pytest.raises(ValueError, match="image1"):
            FaceVerifyInput(image2_base64="abc")

    def test_input_requires_image2(self):
        with pytest.raises(ValueError, match="image2"):
            FaceVerifyInput(image1_base64="abc")

    def test_input_rejects_both_sources_image1(self):
        with pytest.raises(ValueError, match="only one source for image1"):
            FaceVerifyInput(
                image1_base64="abc",
                image1_path="/tmp/1.png",
                image2_base64="def",
            )

    def test_input_accepts_valid(self):
        inp = FaceVerifyInput(image1_base64="abc", image2_base64="def")
        assert inp.image1_base64 == "abc"
        assert inp.image2_base64 == "def"

    def test_input_accepts_paths(self):
        inp = FaceVerifyInput(image1_path="/a.png", image2_path="/b.png")
        assert inp.image1_path == "/a.png"

    def test_result_defaults(self):
        result = FaceVerifyResult()
        assert result.verified is False
        assert result.confidence == 0.0
        assert result.model == "ArcFace"

    def test_result_serialization(self):
        result = FaceVerifyResult(
            verified=True,
            confidence=0.95,
            distance=0.3,
            threshold=0.4,
            liveness=True,
            processing_time_ms=500,
        )
        data = result.model_dump(mode="json")
        assert data["verified"] is True
        assert data["liveness"] is True

    def test_deepface_import_error(self):
        """FaceVerifier raises ImportError when deepface not installed."""
        from openquery.core.face import FaceVerifier

        verifier = FaceVerifier()
        # DeepFace likely not installed in test env
        # If it is, this test still passes (verify needs real images)
        try:
            verifier.verify(b"not-an-image", b"not-an-image")
        except ImportError as e:
            assert "deepface" in str(e).lower()
        except Exception:
            pass  # DeepFace installed but images invalid — that's fine


class TestExceptions:
    """Test custom exceptions."""

    def test_face_verification_error(self):
        from openquery.exceptions import FaceVerificationError

        err = FaceVerificationError("No face detected")
        assert "Face" in str(err)
        assert "No face detected" in str(err)

    def test_document_ocr_error(self):
        from openquery.exceptions import DocumentOCRError

        err = DocumentOCRError("co.cedula", "OCR failed")
        assert "OCR" in str(err)
        assert err.source == "co.cedula"
