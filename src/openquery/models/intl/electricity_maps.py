"""Electricity Maps data model — carbon intensity of electricity."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IntlElectricityMapsResult(BaseModel):
    """Electricity Maps carbon intensity result.

    Source: https://api.electricitymap.org/v3/carbon-intensity/latest
    """

    zone: str = ""
    carbon_intensity: str = ""
    fossil_fuel_percentage: str = ""
    measurement_datetime: str = ""
    details: str = ""
    queried_at: datetime = Field(default_factory=datetime.now)
    audit: Any | None = Field(default=None, exclude=True)
