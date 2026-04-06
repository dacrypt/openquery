"""ICBF data model — Colombian child welfare checks."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IcbfResult(BaseModel):
    """ICBF child welfare check result.

    Source: https://www.icbf.gov.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    total_records: int = 0
    details: dict = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
