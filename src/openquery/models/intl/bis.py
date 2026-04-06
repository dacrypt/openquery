"""BIS statistics data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BisDataPoint(BaseModel):
    """A single observation from the BIS statistics API."""

    period: str = ""
    value: str = ""


class BisResult(BaseModel):
    """BIS (Bank for International Settlements) statistics query result.

    Source: https://data.bis.org/api/v2/
    Docs: https://www.bis.org/statistics/sdmxfaq.htm
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    dataset: str = ""
    dimensions: str = ""
    data_points: list[BisDataPoint] = Field(default_factory=list)
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
