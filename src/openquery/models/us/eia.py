"""EIA energy data model — US electricity/fuel prices."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EiaDataPoint(BaseModel):
    """A single monthly electricity price observation."""

    period: str = ""
    price: str = ""


class UsEiaResult(BaseModel):
    """EIA electricity retail sales data result.

    Source: https://api.eia.gov/v2/electricity/retail-sales/data/
    """

    state: str = ""
    sector: str = ""
    data_points: list[EiaDataPoint] = Field(default_factory=list)
    details: str = ""
    queried_at: datetime = Field(default_factory=datetime.now)
    audit: Any | None = Field(default=None, exclude=True)
