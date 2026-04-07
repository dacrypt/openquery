"""US auto sales data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AutoSalesDataPoint(BaseModel):
    """A single auto sales observation."""

    date: str = ""
    value: str = ""
    units: str = "millions of units, SAAR"


class AutoSalesResult(BaseModel):
    """US auto sales query result.

    Source: https://api.stlouisfed.org/fred/series/observations
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    series_id: str = ""
    series_name: str = ""
    frequency: str = "monthly"
    total_observations: int = 0
    data_points: list[AutoSalesDataPoint] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
