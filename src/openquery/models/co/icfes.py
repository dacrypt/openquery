"""ICFES exam results data model — Colombia."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IcfesResult(BaseModel):
    """ICFES exam results lookup.

    Source: https://www.icfes.gov.co/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    documento: str = ""
    nombre: str = ""
    exam_type: str = ""
    score: str = ""
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
