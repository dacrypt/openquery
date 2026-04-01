"""EPA Fuel Economy data model — US vehicle efficiency ratings."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EpaVehicle(BaseModel):
    """An EPA fuel economy vehicle record."""

    vehicle_id: str = ""
    make: str = ""
    model: str = ""
    year: str = ""
    fuel_type: str = ""
    city_mpg: str = ""
    highway_mpg: str = ""
    combined_mpg: str = ""
    co2_grams_mile: str = ""
    annual_fuel_cost: str = ""
    range_miles: str = ""
    cylinders: str = ""
    displacement: str = ""
    drive: str = ""
    transmission: str = ""


class EpaFuelEconomyResult(BaseModel):
    """EPA fuel economy lookup results.

    Source: https://www.fueleconomy.gov/ws/rest/vehicle/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    make: str = ""
    model: str = ""
    year: str = ""
    total: int = 0
    vehicles: list[EpaVehicle] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
