"""Puerto Rico ASUME child support model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PrAsumeResult(BaseModel):
    """Puerto Rico ASUME child support case result.

    Source: https://www.asume.pr.gov/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    case_number: str = ""
    status: str = ""
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
