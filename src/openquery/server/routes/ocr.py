"""Document OCR endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from openquery.models.ocr import OCRInput, OCRResult

router = APIRouter()


@router.post("/ocr/extract", response_model=OCRResult)
async def ocr_extract(req: OCRInput):
    """Extract structured data from an ID document image."""
    from openquery.core.document_ocr import DocumentOCR

    ocr = DocumentOCR()
    if req.image_base64:
        return ocr.extract_from_base64(req.image_base64, req.document_type)
    else:
        return ocr.extract_from_path(req.image_path, req.document_type)
