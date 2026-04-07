"""Fuel prices data model — World Bank global fuel prices."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class FuelPriceDataPoint(BaseModel):
    """A single monthly fuel price observation."""

    date: str = ""
    price: str = ""
    currency: str = "USD"


class IntlFuelPricesResult(BaseModel):
    """World Bank global fuel prices result.

    Source: https://api.worldbank.org/v2/country/{iso2}/indicator/EP.PMP.SGAS.CD
    """

    country_code: str = ""
    fuel_type: str = ""
    data_points: list[FuelPriceDataPoint] = Field(default_factory=list)
    details: str = ""
    queried_at: datetime = Field(default_factory=datetime.now)
    audit: Any | None = Field(default=None, exclude=True)
