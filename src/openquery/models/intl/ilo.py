"""ILO labor statistics data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IloDataPoint(BaseModel):
    """A single time period/value data point from the ILO API."""

    period: str = ""
    value: str = ""


class IloResult(BaseModel):
    """ILO labor statistics query result.

    Source: https://ilostat.ilo.org/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    country_code: str = ""
    indicator: str = ""
    data_points: list[IloDataPoint] = Field(default_factory=list)
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
