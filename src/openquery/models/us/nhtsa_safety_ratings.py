"""NHTSA Safety Ratings data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NhtsaSafetyRating(BaseModel):
    """Individual vehicle safety rating."""

    vehicle_id: int = 0
    vehicle_description: str = ""
    overall_rating: str = ""
    front_crash_rating: str = ""
    front_crash_driver_rating: str = ""
    front_crash_passenger_rating: str = ""
    side_crash_rating: str = ""
    side_crash_driver_rating: str = ""
    side_crash_passenger_rating: str = ""
    rollover_rating: str = ""
    rollover_probability: float = 0.0
    side_pole_rating: str = ""
    dynamic_tip_result: str = ""
    front_crash_picture: str = ""
    front_crash_video: str = ""
    side_crash_picture: str = ""
    side_crash_video: str = ""
    side_pole_picture: str = ""
    side_pole_video: str = ""
    electronic_stability_control: str = ""
    forward_collision_warning: str = ""
    lane_departure_warning: str = ""
    complaints_count: int = 0
    recalls_count: int = 0
    investigation_count: int = 0


class NhtsaSafetyRatingsResult(BaseModel):
    """NHTSA NCAP crash test safety ratings result.

    Source: https://api.nhtsa.gov/SafetyRatings/
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    make: str = ""
    model: str = ""
    model_year: str = ""
    ratings: list[NhtsaSafetyRating] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
