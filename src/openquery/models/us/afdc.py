"""AFDC Alternative Fuels Station data model — US EV charging stations."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AfdcStation(BaseModel):
    """An EV charging station from the AFDC/NREL database."""

    name: str = ""
    street: str = ""
    city: str = ""
    state: str = ""
    zip: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    ev_network: str = ""
    ev_connector_types: list[str] = Field(default_factory=list)
    ev_level2_count: int = 0
    ev_dc_fast_count: int = 0
    ev_pricing: str = ""
    status: str = ""


class AfdcResult(BaseModel):
    """AFDC EV station search result.

    Source: https://developer.nrel.gov/api/alt-fuel-stations/v1.json
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    search_params: str = ""
    total_stations: int = 0
    stations: list[AfdcStation] = Field(default_factory=list)
    audit: Any | None = Field(default=None, exclude=True)
