"""Ship Tracking data model — Global vessel position tracking."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class VesselPosition(BaseModel):
    """A vessel's current position."""

    latitude: float = 0.0
    longitude: float = 0.0
    speed_knots: float = 0.0
    course: float = 0.0


class Vessel(BaseModel):
    """A tracked vessel."""

    name: str = ""
    imo: str = ""
    mmsi: str = ""
    position: VesselPosition = Field(default_factory=VesselPosition)
    tracking_url: str = ""


class ShipTrackingResult(BaseModel):
    """Vessel position tracking results.

    Source: https://shipinfo.net/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    query: str = ""
    total: int = 0
    vessels: list[Vessel] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
