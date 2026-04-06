"""CAF Development Bank data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CafDataPoint(BaseModel):
    """A single observation from the CAF data portal."""

    period: str = ""
    value: str = ""


class CafResult(BaseModel):
    """CAF (Development Bank of Latin America) query result.

    Source: https://www.caf.com/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    indicator: str = ""
    data_points: list[CafDataPoint] = Field(default_factory=list)
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
