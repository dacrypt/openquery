"""NHTSA VIN Decode data model — US vehicle identification number decoder."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NhtsaVinResult(BaseModel):
    """NHTSA vPIC VIN decode result.

    Source: https://vpic.nhtsa.dot.gov/api/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    vin: str = ""
    make: str = ""
    model: str = ""
    model_year: str = ""
    body_class: str = ""
    vehicle_type: str = ""
    plant_city: str = ""
    plant_country: str = ""
    manufacturer: str = ""
    fuel_type: str = ""
    engine_cylinders: str = ""
    displacement_l: str = ""
    drive_type: str = ""
    gvwr: str = ""
    electrification: str = ""
    battery_kwh: str = ""
    all_fields: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
