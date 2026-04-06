"""Chile DICOM data model — Equifax credit report public summary."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DicomResult(BaseModel):
    """DICOM/Equifax credit report public summary result.

    Source: https://www.equifax.cl/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    rut: str = ""
    dicom_status: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
