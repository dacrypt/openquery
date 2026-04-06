"""CITV data model — Peru vehicle technical inspection (MTC)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CitvResult(BaseModel):
    """Vehicle technical inspection (CITV) record from Peru's MTC.

    Source: https://rec.mtc.gob.pe/Citv/ArConsultaCitv
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    placa: str = ""
    citv_valid: bool = False
    expiration_date: str = ""
    inspection_center: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
