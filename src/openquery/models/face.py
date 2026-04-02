"""Face verification models."""

from __future__ import annotations

from pydantic import BaseModel, model_validator


class FaceVerifyInput(BaseModel):
    """Input for face verification."""

    image1_base64: str | None = None
    image1_path: str | None = None
    image2_base64: str | None = None
    image2_path: str | None = None

    @model_validator(mode="after")
    def _check_image_sources(self):
        if not self.image1_base64 and not self.image1_path:
            raise ValueError("Provide either image1_base64 or image1_path")
        if self.image1_base64 and self.image1_path:
            raise ValueError("Provide only one source for image1")
        if not self.image2_base64 and not self.image2_path:
            raise ValueError("Provide either image2_base64 or image2_path")
        if self.image2_base64 and self.image2_path:
            raise ValueError("Provide only one source for image2")
        return self


class FaceVerifyResult(BaseModel):
    """Result of face verification."""

    verified: bool = False
    confidence: float = 0.0
    distance: float = 0.0
    threshold: float = 0.0
    model: str = "ArcFace"
    liveness: bool = False
    processing_time_ms: int = 0
