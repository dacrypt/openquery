"""Federal Reserve FRED data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class FredDataPoint(BaseModel):
    """A single observation from the FRED API."""

    date: str = ""
    value: str = ""


class FredResult(BaseModel):
    """Federal Reserve FRED economic time series query result.

    Source: https://api.stlouisfed.org/fred/
    Docs: https://fred.stlouisfed.org/docs/api/fred/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    series_id: str = ""
    series_name: str = ""
    data_points: list[FredDataPoint] = Field(default_factory=list)
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
