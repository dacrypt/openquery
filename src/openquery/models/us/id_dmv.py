"""Idaho DMV vehicle status data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IdDmvResult(BaseModel):
    """Idaho DMV title and registration status result.

    Sources:
    - Title: https://dmvonline.itd.idaho.gov/OpenServices/OpenVehicleServices/CheckTitleStatus
    - Registration: https://dmvonline.itd.idaho.gov/OpenServices/OpenVehicleServices/CheckRegistration
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    vin: str = ""
    title_status: str = ""
    registration_status: str = ""
    vehicle_description: str = ""
    details: dict[str, str] = Field(default_factory=dict)
    audit: Any | None = Field(default=None, exclude=True)
