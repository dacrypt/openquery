"""Bureau of Labor Statistics data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BlsDataPoint(BaseModel):
    """A single observation from the BLS time series API."""

    year: str = ""
    period: str = ""
    value: str = ""


class BlsResult(BaseModel):
    """BLS (Bureau of Labor Statistics) time series query result.

    Source: https://api.bls.gov/publicAPI/v2/timeseries/data/
    Docs: https://www.bls.gov/developers/api_signature_v2.htm
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    series_id: str = ""
    series_name: str = ""
    data_points: list[BlsDataPoint] = Field(default_factory=list)
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
