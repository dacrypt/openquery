"""IDB (Inter-American Development Bank) data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IdbDataPoint(BaseModel):
    """A single year/value data point from the IDB API."""

    year: str = ""
    value: str = ""


class IdbResult(BaseModel):
    """IDB (Inter-American Development Bank) indicator query result.

    Source: https://data.iadb.org/
    Docs: https://data.iadb.org/DataCatalog/Dataset
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    country_code: str = ""
    indicator: str = ""
    data_points: list[IdbDataPoint] = Field(default_factory=list)
    details: str = ""
    audit: Any | None = Field(default=None, exclude=True)
