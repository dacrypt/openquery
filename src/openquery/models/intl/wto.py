"""WTO trade profiles / tariff data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WtoDataPoint(BaseModel):
    """A single data point from the WTO timeseries API."""

    year: str = ""
    value: str = ""
    indicator: str = ""
    partner: str = ""


class WtoResult(BaseModel):
    """WTO timeseries trade data query result.

    Source: https://api.wto.org/timeseries/v1/
    Docs: https://apiportal.wto.org/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    reporter: str = ""
    indicator_code: str = ""
    total: int = 0
    data_points: list[WtoDataPoint] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
