"""OICA global vehicle production/sales data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class OicaCountryData(BaseModel):
    """Vehicle production/sales data for a single country/year."""

    country: str = ""
    year: str = ""
    passenger_cars: int = 0
    commercial_vehicles: int = 0
    total: int = 0


class OicaResult(BaseModel):
    """OICA global vehicle production/sales query result.

    Source: https://oica.net/sales-statistics/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_term: str = ""
    total_countries: int = 0
    data: list[OicaCountryData] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
