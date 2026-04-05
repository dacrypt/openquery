"""Florida DHSMV vehicle check data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class FlDmvResult(BaseModel):
    """Florida DHSMV vehicle title/registration check result.

    Source: https://services.flhsmv.gov/mvcheckweb/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_type: str = ""  # "vin" or "plate"
    search_value: str = ""
    title_status: str = ""
    brand_history: list[str] = Field(default_factory=list)
    odometer: str = ""
    registration_status: str = ""
    vehicle_description: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
