"""Face verification endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from openquery.models.face import FaceVerifyInput, FaceVerifyResult

router = APIRouter()


@router.post("/face/verify", response_model=FaceVerifyResult)
async def face_verify(req: FaceVerifyInput):
    """Verify identity by comparing two face images."""
    import base64
    from pathlib import Path

    from openquery.core.face import FaceVerifier

    verifier = FaceVerifier()

    img1 = (
        base64.b64decode(req.image1_base64) if req.image1_base64
        else Path(req.image1_path).read_bytes()
    )
    img2 = (
        base64.b64decode(req.image2_base64) if req.image2_base64
        else Path(req.image2_path).read_bytes()
    )

    return verifier.verify(img1, img2)
