"""Document OCR models — extract structured data from ID documents."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, model_validator


class DocumentTypeOCR(StrEnum):
    """Supported document types for OCR extraction."""

    CO_CEDULA = "co.cedula"
    MX_INE = "mx.ine"
    PE_DNI = "pe.dni"
    CL_CARNET = "cl.carnet"
    PASSPORT_MRZ = "passport.mrz"


class OCRInput(BaseModel):
    """Input for document OCR extraction."""

    image_base64: str | None = None
    image_path: str | None = None
    document_type: DocumentTypeOCR

    @model_validator(mode="after")
    def _check_image_source(self):
        if not self.image_base64 and not self.image_path:
            raise ValueError("Provide either image_base64 or image_path")
        if self.image_base64 and self.image_path:
            raise ValueError("Provide only one of image_base64 or image_path")
        return self


class OCRField(BaseModel):
    """A single extracted field."""

    name: str
    value: str
    confidence: float = 0.0


class OCRResult(BaseModel):
    """Result of document OCR extraction."""

    document_type: DocumentTypeOCR
    fields: dict[str, str]
    confidence: float = 0.0
    raw_text: str = ""
    processing_time_ms: int = 0
