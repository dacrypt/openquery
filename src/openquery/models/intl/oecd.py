"""OECD statistics data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class OecdDataPoint(BaseModel):
    """A single time-period/value data point from the OECD SDMX API."""

    period: str = ""
    value: str = ""


class OecdResult(BaseModel):
    """OECD statistics query result.

    Source: https://sdmx.oecd.org/public/rest/
    Docs: https://data.oecd.org/api/sdmx-json-documentation/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    country_code: str = ""
    indicator_code: str = ""
    data_points: list[OecdDataPoint] = Field(default_factory=list)
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
