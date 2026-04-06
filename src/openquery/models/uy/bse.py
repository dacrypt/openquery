"""Uruguay BSE mandatory vehicle insurance model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class UyBseResult(BaseModel):
    """Uruguay BSE vehicle SOA insurance status result.

    Source: https://www.bse.com.uy/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    placa: str = ""
    insurance_status: str = ""
    policy_valid: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
